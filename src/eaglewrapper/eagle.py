"""The :class:`Eagle` class: Eagle's V1 (legacy) API and the library-folder reader.

V1 reference: https://api.eagle.cool/ (Eagle 1.11 Build 21 and later; Eagle now calls it legacy).

The V1 methods keep the behaviour of 1.1.1: when Eagle reports a failure they return
``False`` or ``None`` (and log a warning) instead of raising. Pass ``raise_errors=True``
to get an :class:`~eaglewrapper.errors.EagleAPIError` instead.
"""
from typing import Any, Dict, List, Optional, Sequence, Union
from urllib.parse import urlsplit

import requests
from loguru import logger

from . import _library
from .client import DEFAULT_HOST, DEFAULT_PORT, EagleClient, Params, error_message, is_success
from .errors import EagleAPIError


class ImageData:
    """
    A class to represent image data for adding images to Eagle.

    Attributes:
        url (str): Required. The URL of the image to be added. Supports http, https, and base64.
        name (str): Required. The name of the image to be added.
        website (str): The address of the image source.
        tags (list): Tags for the image.
        annotation (str): The annotation for the image.
        modificationTime (int): The creation date of the image. Can be used to alter the image's sorting order in Eagle.
        headers (dict): Optional. Customize the HTTP headers properties. Can be used to bypass security on certain websites.
    """
    def __init__(self, url: str, name: str, website: Optional[str] = '', tags: Optional[List[str]] = None,
                 annotation: Optional[str] = '', modificationTime: Optional[int] = None,
                 headers: Optional[Dict[str, str]] = None):
        """
        Initializes the ImageData instance with the given attributes.

        Args:
            url (str): Required. The URL of the image to be added. Supports http, https, and base64.
            name (str): Required. The name of the image to be added.
            website (str, optional): The address of the image source. Defaults to an empty string.
            tags (list, optional): Tags for the image. Defaults to an empty list.
            annotation (str, optional): The annotation for the image. Defaults to an empty string.
            modificationTime (int, optional): The creation date of the image. Can be used to alter the image's
                sorting order in Eagle. Defaults to None.
            headers (dict, optional): Customize the HTTP headers properties. Can be used to bypass security on
                certain websites. Defaults to an empty dictionary.

        Raises:
            ValueError: If the URL or name is empty.
        """
        if not url:
            raise ValueError("URL cannot be empty.")
        if not name:
            raise ValueError("Name cannot be empty.")

        self.url = url
        self.name = name
        self.website = website
        self.tags = [] if tags is None else tags
        self.annotation = annotation
        self.modificationTime = modificationTime
        self.headers = {} if headers is None else headers

    def to_dict(self) -> dict:
        """The fields as the JSON object Eagle expects (a copy)."""
        return dict(self.__dict__)


def _path_item(path: str, name: str, website: Optional[str], annotation: Optional[str],
               tags: Optional[List[str]]) -> Dict[str, Any]:
    """An item for addFromPath(s): the ImageData fields with ``path`` instead of ``url``."""
    item = ImageData(url=path, name=name, website=website, tags=tags, annotation=annotation).to_dict()
    item['path'] = item.pop('url')
    return item


class Eagle:
    """Talk to a running Eagle app.

    Args:
        domain: Scheme and host of Eagle's API server. Defaults to ``http://localhost``.
        port: Port of Eagle's API server. Defaults to ``41595``.
        token: API token, needed only when Eagle runs on another device (Eagle >
            Preferences > Developer). Sent as ``?token=`` on every request. When omitted,
            the ``EAGLE_API_TOKEN`` environment variable is used if it is set.
        base_url: The whole address instead of ``domain`` and ``port``, e.g.
            ``http://192.168.1.20:41595``.
        timeout: Seconds to wait for Eagle. ``None`` (default) waits as long as it takes.
        session: A ``requests.Session`` to send requests with, e.g. to reuse connections.
        raise_errors: When ``True``, the V1 methods raise
            :class:`~eaglewrapper.errors.EagleAPIError` when Eagle reports a failure,
            instead of returning ``False``/``None``.
    """

    def __init__(self, domain: str = DEFAULT_HOST, port: int = DEFAULT_PORT, *, token: Optional[str] = None,
                 base_url: Optional[str] = None, timeout: Optional[float] = None,
                 session: Optional[requests.Session] = None, raise_errors: bool = False):
        self.domain = domain
        self.port = port  # type: Optional[int]
        if base_url is not None:
            parts = urlsplit(base_url)
            self.domain = '{}://{}'.format(parts.scheme, parts.hostname)
            self.port = parts.port
        else:
            base_url = '{}:{}'.format(domain, port)
        self.raise_errors = raise_errors
        self._client = EagleClient(base_url, token=token, timeout=timeout, session=session)

    def __repr__(self) -> str:
        return 'Eagle({!r})'.format(self.host)

    @property
    def host(self) -> str:
        """The address requests go to, e.g. ``http://localhost:41595``."""
        return self._client.base_url

    @host.setter
    def host(self, value: str) -> None:
        self._client.base_url = value.rstrip('/')

    @property
    def token(self) -> Optional[str]:
        """The API token sent with every request, or ``None``."""
        return self._client.token

    @token.setter
    def token(self, value: Optional[str]) -> None:
        self._client.token = value

    def check_success(self, response: Union[requests.Response, Dict[str, Any]]) -> bool:
        """
        Check if the API response status is 'success'.

        Args:
            response (Response or dict): The response object from an API call, or its decoded JSON.

        Returns:
            bool: True if the status is 'success', otherwise False.
        """
        payload = response if isinstance(response, dict) else response.json()
        return is_success(payload)

    # =================================================
    # Shared request handling for the V1 methods
    # =================================================

    def _failed(self, path: str, payload: Any, status_code: Optional[int] = None) -> None:
        """Report a V1 failure: raise with ``raise_errors``, otherwise log a warning."""
        message = '{} failed: {}'.format(path, error_message(payload))
        if self.raise_errors:
            raise EagleAPIError(message, endpoint=path, status_code=status_code, payload=payload)
        logger.warning('[Eagle] {}', message)

    def _ok(self, method: str, path: str, params: Params = None, body: Any = None) -> bool:
        """Call a V1 endpoint that answers only with a status; return whether it succeeded."""
        payload, status_code = self._client.exchange(method, path, params, body)
        if is_success(payload):
            return True
        self._failed(path, payload, status_code)
        return False

    def _data(self, method: str, path: str, params: Params = None, body: Any = None,
              none_on_error: bool = False) -> Any:
        """Call a V1 endpoint and return its ``data`` (1.1.1 returned it even on failure)."""
        payload, status_code = self._client.exchange(method, path, params, body)
        if not is_success(payload):
            self._failed(path, payload, status_code)
            if none_on_error:
                return None
        return payload.get('data') if isinstance(payload, dict) else None

    # =================================================
    # NOT IN API methods
    # =================================================

    def get_img_info_from_lib_path(self, library_path: str, name_start_filters: Optional[Sequence[str]] = None,
                                   max_workers: int = 4) -> List[Dict[str, Any]]:
        """
        Get all images' information (metadata) from the path of the source library.

        This reads ``images/<id>.info/metadata.json`` files from the library folder directly,
        so Eagle does not need to be running and it is faster than the API for big libraries.
        The library's own ``metadata.json`` (folders, smart folders, ...) is not returned.

        For example, there is a path of a library at '/path/to/your/test.library'.

        Args:
            library_path (str): The path of the source library.
            name_start_filters (list, optional): Name prefixes to filter images by; a name has to start with
                every one of them. Defaults to no filter.
            max_workers (int, optional): The number of concurrent workers. Defaults to 4.

        Returns:
            list: A list of dictionaries containing the metadata of the images.
        """
        return _library.read_items(library_path, name_start_filters, max_workers)

    def set_tag_with_id(self, item_id: str, tags: List[str]) -> Optional[Dict[str, Any]]:
        """
        Set tags to an image with its ID by using `update` API.

        API DOC: https://api.eagle.cool/item/update

        Args:
            item_id (str): The ID of the image to be updated.
            tags (list): A list of tags to be associated with the image.

        Returns:
            dict: The updated item.

        Raises:
            EagleAPIError: Eagle could not update the item.
        """
        return self.update_item(item_id, tags)

    def get_img_list_info(self, max_image_number: int, name_start_filter: str = '') -> Optional[List[Dict[str, Any]]]:
        """
        Get a list of images' information up to the specified maximum number of images.

        API DOC: https://api.eagle.cool/item/list

        Args:
            max_image_number (int): The maximum number of images to retrieve.
            name_start_filter (str, optional): A string to filter images by name prefix. Defaults to an empty string.

        Returns:
            list: The matching images, or None if Eagle reported a failure.
        """
        data = self._data('GET', '/api/item/list', {'limit': max_image_number})
        if name_start_filter != '' and data is not None:
            data = [d for d in data if str(d.get('name') or '').startswith(name_start_filter)]
        return data

    # =================================================
    # Application methods
    # =================================================

    def get_application_info(self) -> Optional[Dict[str, Any]]:
        """
        Get detailed information on the Eagle App currently running.

        API DOC: https://api.eagle.cool/application/info

        Returns:
            dict: Information on the Eagle App, such as version, buildVersion, execPath, and platform.
        """
        return self._data('GET', '/api/application/info')

    # =================================================
    # Image (Item) methods
    # =================================================

    def add_from_url(self, url: str, name: str, tags: Optional[List[str]] = None, website: str = '',
                     annotation: str = '', modification_time: Optional[int] = None, folder_id: Optional[str] = None,
                     headers: Optional[Dict[str, str]] = None, star: Optional[int] = None) -> bool:
        """
        Add a new image or materials from the given URL.

        API DOC: https://api.eagle.cool/item/add-from-url

        Args:
            url (str): The URL of the image or materials to be added. Supports http, https and base64.
            name (str): The name to be assigned to the item.
            tags (list, optional): A list of tags to be associated with the item. Defaults to an empty list.
            website (str, optional): The website where the image or materials are from. Defaults to ''.
            annotation (str, optional): Any additional annotation or description for the item. Defaults to ''.
            modification_time (int, optional): The creation date of the image (milliseconds since the epoch).
            folder_id (str, optional): If this parameter is defined, the image will be added to the corresponding folder.
            headers (dict, optional): Customize the HTTP headers properties, this could be used to circumvent the
                security of certain websites.
            star (int, optional): Rating from 0 to 5. Only sent when given.

        Returns:
            bool: True if Eagle accepted the image.

        Raises:
            ValueError: If the URL or name is empty.
        """
        data = ImageData(url=url, name=name, website=website, tags=tags, annotation=annotation,
                         modificationTime=modification_time, headers=headers).to_dict()
        if folder_id is not None:
            data['folderId'] = folder_id
        if star is not None:
            data['star'] = star
        return self._ok('POST', '/api/item/addFromURL', body=data)

    def add_from_urls(self, items: List[Dict[str, Any]], folder_id: Optional[str] = None) -> bool:
        """
        Add multiple images from URLs to Eagle.

        API DOC: https://api.eagle.cool/item/add-from-urls

        Args:
            items (list): The array object made up of multiple items. Each item is a dictionary with keys:
                - url (str): Required, the URL of the image to be added. Supports http, https, base64.
                - name (str): Required, the name of the image to be added.
                - website (str, optional): The address of the source of the image.
                - annotation (str, optional): The annotation for the image.
                - tags (list, optional): Tags for the image.
                - modificationTime (int, optional): The creation date of the image.
                  `modification_time` is accepted as well.
                - headers (dict, optional): Customize the HTTP headers properties.
            folder_id (str, optional): If the parameter is defined, images will be added to the corresponding folder.

        Returns:
            bool: True if Eagle accepted the images.
        """
        data = {'items': [
            ImageData(
                url=item['url'],
                name=item['name'],
                website=item.get('website', ''),
                tags=item.get('tags'),
                annotation=item.get('annotation', ''),
                modificationTime=item.get('modificationTime', item.get('modification_time')),
                headers=item.get('headers'),
            ).to_dict()
            for item in items
        ]}  # type: Dict[str, Any]
        if folder_id is not None:
            data['folderId'] = folder_id
        return self._ok('POST', '/api/item/addFromURLs', body=data)

    def add_from_path(self, path: str, name: str, website: Optional[str] = None,
                      annotation: Optional[str] = None, tags: Optional[List[str]] = None,
                      folder_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Add a local file to Eagle.

        API DOC: https://api.eagle.cool/item/add-from-path

        Args:
            path (str): Required, the path of the local file.
            name (str): Required, the name of the image to be added.
            website (str, optional): The address of the source of the image.
            annotation (str, optional): The annotation for the image.
            tags (List[str], optional): Tags for the image.
            folder_id (str, optional): If this parameter is defined, the image will be added to the corresponding folder.

        Returns:
            dict: Eagle's whole reply, e.g. ``{'status': 'success'}``. Unlike the other add methods
            this is not a bool (kept as in 1.1.1), so test ``reply['status'] == 'success'`` or
            ``eagle.check_success(reply)`` rather than the reply itself: a dict is always truthy.
            With ``raise_errors=True`` a failure raises instead.
        """
        data = _path_item(path, name, website, annotation, tags)
        data['folderId'] = folder_id
        payload, status_code = self._client.exchange('POST', '/api/item/addFromPath', body=data)
        if not is_success(payload):
            self._failed('/api/item/addFromPath', payload, status_code)
        return payload

    def add_from_paths(self, items: List[Dict[str, Any]], folder_id: Optional[str] = None) -> bool:
        """
        Add multiple local files to Eagle.

        API DOC: https://api.eagle.cool/item/add-from-paths

        Args:
            items (List[Dict]): A list of dictionaries containing the following keys:
                - path (str): The path of the local file.
                - name (str): The name of the image to be added.
                - website (str, optional): The address of the source of the image.
                - annotation (str, optional): The annotation for the image.
                - tags (List[str], optional): Tags for the image.
            folder_id (str, optional): If this parameter is defined, the images will be added to the corresponding folder.

        Returns:
            bool: True if Eagle accepted the files.
        """
        data = {'items': [
            _path_item(item['path'], item['name'], item.get('website', ''), item.get('annotation', ''),
                       item.get('tags'))
            for item in items
        ]}  # type: Dict[str, Any]
        if folder_id is not None:
            data['folderId'] = folder_id
        return self._ok('POST', '/api/item/addFromPaths', body=data)

    def add_bookmark(self, url: str, name: str, tags: Optional[List[str]] = None,
                     thumbnail_base64: Optional[str] = None, modification_time: Optional[int] = None,
                     folder_id: Optional[str] = None) -> bool:
        """
        Save the link in the URL form to Eagle.

        API DOC: https://api.eagle.cool/item/add-bookmark

        Args:
            url (str): The link of the image to be saved. Supports http, https, base64.
            name (str): The name of the image to be added.
            tags (List[str], optional): Tags for the image.
            thumbnail_base64 (str, optional): The thumbnail of the bookmark. Must be in base64 format.
            modification_time (int, optional): The creation date of the images. The parameter can be used to alter the
                                               images' sorting order in Eagle.
            folder_id (str, optional): If this parameter is defined, the image will be added to the corresponding folder.

        Returns:
            bool: True if Eagle saved the bookmark.
        """
        data = {
            "url": url,
            "name": name,
            "tags": tags or [],
            "base64": thumbnail_base64,
            "modificationTime": modification_time,
            "folderId": folder_id
        }
        return self._ok('POST', '/api/item/addBookmark', body=data)

    def get_item_info(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get properties of the specified file, including the file name, tags, categorizations, folders, dimensions, etc.

        API DOC: https://api.eagle.cool/item/info

        Args:
            item_id (str): ID of the file.

        Returns:
            Optional[Dict[str, Any]]: The properties of the specified file, or None if unsuccessful.
        """
        return self._data('GET', '/api/item/info', {'id': item_id}, none_on_error=True)

    def get_thumbnail_path(self, item_id: str) -> Optional[str]:
        """
        Get the path of the thumbnail of the specified file.

        API DOC: https://api.eagle.cool/item/thumbnail

        Args:
            item_id (str): ID of the file.

        Returns:
            Optional[str]: The thumbnail path of the specified file, or None if unsuccessful.
        """
        return self._data('GET', '/api/item/thumbnail', {'id': item_id}, none_on_error=True)

    def list_items(self, limit: int = 200, offset: int = 0, order_by: Optional[str] = None,
                   keyword: Optional[str] = None, ext: Optional[str] = None, tags: Optional[List[str]] = None,
                   folders: Optional[List[str]] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Get items that match the filter condition.

        API DOC: https://api.eagle.cool/item/list

        Args:
            limit (int): The number of items to be displayed. The default number is 200.
            offset (int): Offset a collection of results from the api. Start with 0.
            order_by (Optional[str]): The sorting order. CREATEDATE, FILESIZE, NAME, RESOLUTION, add a minus sign for
                descending order: -FILESIZE.
            keyword (Optional[str]): Filter by the keyword.
            ext (Optional[str]): Filter by the extension type, e.g.: jpg, png.
            tags (Optional[List[str]]): Filter by tags.
            folders (Optional[List[str]]): Filter by Folders.

        Returns:
            list: The matching items.
        """
        params = {'limit': limit, 'offset': offset}  # type: Dict[str, Any]
        if order_by:
            params['orderBy'] = order_by
        if keyword:
            params['keyword'] = keyword
        if ext:
            params['ext'] = ext
        if tags:
            params['tags'] = ','.join(tags)
        if folders:
            params['folders'] = ','.join(folders)
        return self._data('GET', '/api/item/list', params)

    def move_to_trash(self, item_ids: List[str]) -> bool:
        """
        Move items to trash.

        API DOC: https://api.eagle.cool/item/api-item-movetotrash

        Args:
            item_ids (List[str]): A list of item IDs to be moved to trash.

        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        return self._ok('POST', '/api/item/moveToTrash', body={"itemIds": item_ids})

    def refresh_palette(self, item_id: str) -> bool:
        """
        Re-analysis the color of the file. When changes to the original file were made,
        you can call this function to refresh the Color Analysis.

        API DOC: https://api.eagle.cool/item/refresh-palette

        Args:
            item_id (str): The item's ID.

        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        return self._ok('POST', '/api/item/refreshPalette', body={"id": item_id})

    def refresh_thumbnail(self, item_id: str) -> bool:
        """
        Re-generate the thumbnail of the file used to display in the List. When changes to
        the original file were made, you can call this function to re-generate the thumbnail,
        the color analysis will also be made.

        API DOC: https://api.eagle.cool/item/refresh-thumbnail

        Args:
            item_id (str): The item's ID.

        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        return self._ok('POST', '/api/item/refreshThumbnail', body={"id": item_id})

    def update_item(self, item_id: str, tags: Optional[List[str]] = None, annotation: Optional[str] = None,
                    url: Optional[str] = None, star: Optional[int] = None) -> Dict[str, Any]:
        """
        Modify data of specified fields of the item.

        API DOC: https://api.eagle.cool/item/update

        Args:
            item_id (str): Required, the ID of the item to be modified.
            tags (list): Optional, tags.
            annotation (str): Optional, annotations.
            url (str): Optional, the source url.
            star (int): Optional, ratings.

        Returns:
            dict: Updated item data.

        Raises:
            EagleAPIError: Eagle could not update the item (always raised, as in 1.1.1, where it was a
                plain ``Exception``; ``EagleAPIError`` is a subclass of it).
        """
        data = {"id": item_id}  # type: Dict[str, Any]
        if tags is not None:
            data["tags"] = tags
        if annotation is not None:
            data["annotation"] = annotation
        if url is not None:
            data["url"] = url
        if star is not None:
            data["star"] = star

        payload, status_code = self._client.exchange('POST', '/api/item/update', body=data)
        if not is_success(payload):
            raise EagleAPIError('[Eagle] Failed to update the item: {}'.format(error_message(payload)),
                                endpoint='/api/item/update', status_code=status_code, payload=payload)
        return payload.get("data")

    # =================================================
    # Folder methods
    # =================================================

    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Create a folder. The created folder will be placed at the bottom of the folder list of the current library.

        API DOC: https://api.eagle.cool/folder/create

        Args:
            folder_name (str): The name of the folder to be created.
            parent_id (str, optional): The ID of the parent folder. If not provided, the created folder will be at the
                top level. Defaults to None.

        Returns:
            dict: The created folder.
        """
        data = {'folderName': folder_name}
        if parent_id is not None:
            data['parent'] = parent_id
        return self._data('POST', '/api/folder/create', body=data)

    def rename_folder(self, folder_id: str, new_name: str) -> Optional[Dict[str, Any]]:
        """
        Rename the specified folder.

        API DOC: https://api.eagle.cool/folder/rename

        Args:
            folder_id (str): The ID of the folder to be renamed.
            new_name (str): The new name for the folder.

        Returns:
            dict: The renamed folder.
        """
        return self._data('POST', '/api/folder/rename', body={'folderId': folder_id, 'newName': new_name})

    def update_folder(self, folder_id: str, new_name: Optional[str] = None, new_description: Optional[str] = None,
                      new_color: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Update the specified folder.

        API DOC: https://api.eagle.cool/folder/update

        Args:
            folder_id (str): The ID of the folder to be updated.
            new_name (str, optional): The new name for the folder. Defaults to None.
            new_description (str, optional): The new description for the folder. Defaults to None.
            new_color (str, optional): The new color for the folder. Valid options are "red", "orange", "green",
                "yellow", "aqua", "blue", "purple", "pink". Defaults to None.

        Returns:
            dict: The updated folder.
        """
        data = {'folderId': folder_id}
        if new_name is not None:
            data['newName'] = new_name
        if new_description is not None:
            data['newDescription'] = new_description
        if new_color is not None:
            data['newColor'] = new_color
        return self._data('POST', '/api/folder/update', body=data)

    def list_folders(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get the list of folders of the current library.

        API DOC: https://api.eagle.cool/folder/list

        Returns:
            list: The folders, each with its ``children``.
        """
        return self._data('GET', '/api/folder/list')

    def get_recent_folders(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get the list of recently used folders by the user.

        API DOC: https://api.eagle.cool/folder/list-recent

        Returns:
            list: The recently used folders.
        """
        return self._data('GET', '/api/folder/listRecent')

    # =================================================
    # Library methods
    # =================================================

    def get_library_info(self) -> Optional[Dict[str, Any]]:
        """
        Get detailed information of the currently running library. This function can be used to obtain details
        such as All Folders, All Smart Folders, All Tag Groups, Quick Access, etc.

        API DOC: https://api.eagle.cool/library/info

        Returns:
            dict: Detailed information about the currently running library.
        """
        return self._data('GET', '/api/library/info')

    def get_library_history(self) -> Optional[List[str]]:
        """
        Get the list of libraries recently opened by the Application.

        API DOC: https://api.eagle.cool/library/history

        Returns:
            list: The paths of recently opened libraries.
        """
        return self._data('GET', '/api/library/history')

    def switch_library(self, library_path: str) -> bool:
        """
        Switch the library currently opened by Eagle.

        API DOC: https://api.eagle.cool/library/switch

        Args:
            library_path (str): The path of the library to switch to.

        Returns:
            bool: True if Eagle switched to the library.
        """
        return self._ok('POST', '/api/library/switch', body={"libraryPath": library_path})

    def get_library_icon(self, library_path: str) -> Optional[bytes]:
        """
        Get the icon image of a library.

        API DOC: https://api.eagle.cool/library/icon

        Args:
            library_path (str): The path of the library.

        Returns:
            bytes: The image data, or None if Eagle reported a failure.
        """
        try:
            return self._client.binary('/api/library/icon', {'libraryPath': library_path})
        except EagleAPIError as e:
            self._failed('/api/library/icon', e.payload, e.status_code)
            return None
