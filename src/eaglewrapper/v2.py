"""Eagle's Web API V2 (``/api/v2/...``), available since Eagle 4.0 Build 21.

Reference: https://developer.eagle.cool/web-api

The API is grouped the same way as the official docs, so ``POST /api/v2/item/query``
is ``v2.item.query(...)`` and ``POST /api/v2/tagGroup/addTags`` is
``v2.tag_group.add_tags(...)``. Every method returns the ``data`` part of Eagle's reply
and raises :class:`~eaglewrapper.errors.EagleAPIError` when Eagle reports a failure.

List endpoints are paginated: they return a page dict
``{'data': [...], 'total': 1250, 'offset': 0, 'limit': 50}`` (Eagle's default limit is
50, the maximum 1000). The ``iterate`` methods walk through all pages for you.

Use it through :class:`~eaglewrapper.Eagle` (``Eagle().v2``) or on its own::

    from eaglewrapper import EagleV2
    v2 = EagleV2()
    for item in v2.item.iterate(tags=['cat'], fields=['id', 'name']):
        print(item['name'])
"""
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

import requests

from ._apis import API_V2, api_for_path
from .client import DEFAULT_HOST, DEFAULT_PORT, EagleClient, Params

MAX_LIMIT = 1000
"""The largest ``limit`` Eagle accepts on list endpoints."""

ICON_COLORS = ('red', 'orange', 'yellow', 'green', 'aqua', 'blue', 'purple', 'pink')
"""The folder and smart-folder icon colors Eagle accepts."""

SHAPES = ('square', 'portrait', 'panoramic-portrait', 'landscape', 'panoramic-landscape')
"""The values of the ``shape`` filter of :meth:`ItemAPI.get`."""

Item = Dict[str, Any]
Page = Dict[str, Any]


def _compact(**fields: Any) -> Dict[str, Any]:
    """The given fields without the ones that are ``None`` (= not set)."""
    return {key: value for key, value in fields.items() if value is not None}


def _rows(page: Any) -> Tuple[List[Any], Optional[int]]:
    """The rows of a page and its ``total``; also accepts a plain list."""
    if isinstance(page, dict) and isinstance(page.get('data'), list):
        total = page.get('total')
        return page['data'], total if isinstance(total, int) else None
    if isinstance(page, list):
        return page, None
    return [], None


def _paginate(fetch: Callable[..., Any], offset: int = 0, page_size: int = 200) -> Iterator[Any]:
    """Yield every row of a paginated endpoint, one page of ``page_size`` at a time."""
    if not 1 <= page_size <= MAX_LIMIT:
        raise ValueError('page_size must be between 1 and {}, not {!r}'.format(MAX_LIMIT, page_size))
    while True:
        rows, total = _rows(fetch(offset=offset, limit=page_size))
        for row in rows:
            yield row
        offset += len(rows)
        if not rows:
            return
        if total is not None:
            if offset >= total:
                return
        elif len(rows) < page_size:
            return


class _Section:
    """One group of V2 endpoints, e.g. everything under ``/api/v2/item/``."""

    _prefix = ''

    def __init__(self, client: EagleClient):
        self._client = client

    def __repr__(self) -> str:
        return '<{} {}{}>'.format(type(self).__name__, self._client.base_url, self._path())

    def _path(self, action: str = '') -> str:
        """The full path of one endpoint of this group, e.g. ``/api/v2/item/get``."""
        return API_V2.path('{}/{}'.format(self._prefix, action))

    def _get(self, action: str, params: Params = None) -> Any:
        return self._client.data('GET', self._path(action), _compact(**(params or {})))

    def _post(self, action: str, body: Optional[Dict[str, Any]] = None) -> Any:
        return self._client.data('POST', self._path(action), None, _compact(**(body or {})))


class ItemAPI(_Section):
    """Query, add, modify and manage items. Docs: https://developer.eagle.cool/web-api/api/item"""

    _prefix = 'item'

    def get(self, *, item_id: Optional[str] = None, item_ids: Optional[Sequence[str]] = None,
            is_selected: Optional[bool] = None, is_untagged: Optional[bool] = None,
            is_unfiled: Optional[bool] = None, keywords: Optional[Sequence[str]] = None,
            tags: Optional[Sequence[str]] = None, folders: Optional[Sequence[str]] = None,
            smart_folders: Optional[Sequence[str]] = None, ext: Optional[str] = None,
            annotation: Optional[str] = None, rating: Optional[int] = None, url: Optional[str] = None,
            shape: Optional[str] = None, fields: Optional[Sequence[str]] = None,
            offset: Optional[int] = None, limit: Optional[int] = None) -> Page:
        """List items that match all the given filters (``POST /api/v2/item/get``).

        Args:
            item_id: Only this item.
            item_ids: Only these items.
            is_selected: Only the items currently selected in Eagle.
            is_untagged: Only items without tags.
            is_unfiled: Only items that are in no folder.
            keywords: Keywords to match.
            tags: Tags to match.
            folders: Folder IDs to match.
            smart_folders: Smart folder IDs; an item in any of them matches (Eagle 4.0 Build 22+).
            ext: File extension, e.g. ``'png'``.
            annotation: Annotation text.
            rating: Rating, 0 to 5.
            url: Source URL.
            shape: One of :data:`SHAPES`.
            fields: Return only these fields of each item, e.g. ``['id', 'name']`` (faster).
            offset: Items to skip. Eagle's default is 0.
            limit: Items per page. Eagle's default is 50, the maximum 1000.

        Returns:
            A page: ``{'data': [item, ...], 'total': int, 'offset': int, 'limit': int}``.
        """
        return self._post('get', {
            'id': item_id, 'ids': _list(item_ids), 'isSelected': is_selected, 'isUntagged': is_untagged,
            'isUnfiled': is_unfiled, 'keywords': _list(keywords), 'tags': _list(tags), 'folders': _list(folders),
            'smartFolders': _list(smart_folders), 'ext': ext, 'annotation': annotation, 'rating': rating,
            'url': url, 'shape': shape, 'fields': _list(fields), 'offset': offset, 'limit': limit})

    def iterate(self, page_size: int = 200, offset: int = 0, **filters: Any) -> Iterator[Item]:
        """Yield every item matching the filters of :meth:`get`, fetching ``page_size`` at a time."""
        return _paginate(lambda **page: self.get(**dict(filters, **page)), offset, page_size)

    def get_by_id(self, item_id: str, fields: Optional[Sequence[str]] = None) -> Optional[Item]:
        """One item by ID, or ``None`` if there is no such item."""
        result = self.get(item_id=item_id, fields=fields)
        rows, _ = _rows(result)
        if rows:
            return rows[0]
        if isinstance(result, dict) and result.get('id') == item_id:
            return result
        return None

    def query(self, query: str, *, offset: Optional[int] = None, limit: Optional[int] = None) -> Page:
        """Full-text search over names, tags, annotations, URLs, folder names and more (``POST /api/v2/item/query``).

        The query syntax supports ``cat dog`` (both), ``cat OR dog``, ``-cartoon`` (not),
        ``"orange cat"`` (phrase) and grouping with parentheses.

        Returns:
            A page of items, like :meth:`get`.
        """
        return self._post('query', {'query': query, 'offset': offset, 'limit': limit})

    def iterate_query(self, query: str, page_size: int = 200, offset: int = 0) -> Iterator[Item]:
        """Yield every item that matches a full-text :meth:`query`."""
        return _paginate(lambda **page: self.query(query, **page), offset, page_size)

    def count_all(self) -> int:
        """The number of items in the library (``GET /api/v2/item/countAll``)."""
        return self._get('countAll')

    def add(self, *, url: Optional[str] = None, path: Optional[str] = None, base64: Optional[str] = None,
            bookmark_url: Optional[str] = None, name: Optional[str] = None, tags: Optional[Sequence[str]] = None,
            folders: Optional[Sequence[str]] = None, annotation: Optional[str] = None,
            website: Optional[str] = None, item_id: Optional[str] = None) -> Optional[str]:
        """Add one item from exactly one source (``POST /api/v2/item/add``).

        Args:
            url: Download the image from this URL.
            path: Import this local file.
            base64: Import this Base64-encoded image.
            bookmark_url: Save this URL as a bookmark.
            name: Item name.
            tags: Tags to set.
            folders: IDs of the folders to put the item in.
            annotation: Annotation text.
            website: Source website.
            item_id: Use this ID instead of a generated one.

        Returns:
            The new item's ID.

        Raises:
            ValueError: Not exactly one of ``url``, ``path``, ``base64`` and ``bookmark_url`` was given.
        """
        sources = _compact(url=url, path=path, base64=base64, bookmarkURL=bookmark_url)
        if len(sources) != 1:
            raise ValueError('Give exactly one of url, path, base64 or bookmark_url (got {}).'.format(
                ', '.join(sorted(sources)) or 'none'))
        body = dict(sources, id=item_id, name=name, tags=_list(tags), folders=_list(folders),
                    annotation=annotation, website=website)
        data = self._post('add', body)
        return data.get('id') if isinstance(data, dict) else data

    def add_many(self, items: Sequence[Dict[str, Any]]) -> List[str]:
        """Add up to 1000 items in one request (batch mode of ``POST /api/v2/item/add``).

        Args:
            items: Items in Eagle's format, each with one of ``url``, ``path``, ``base64`` or
                ``bookmarkURL`` plus optional ``name``, ``tags``, ``folders``, ``annotation``,
                ``website`` and ``id``. Sources can be mixed.

        Returns:
            The new items' IDs.
        """
        items = list(items)
        if not 1 <= len(items) <= MAX_LIMIT:
            raise ValueError('add_many takes 1 to {} items, not {}.'.format(MAX_LIMIT, len(items)))
        data = self._post('add', {'items': items})
        return list(data.get('ids') or []) if isinstance(data, dict) else list(data or [])

    def update(self, item_id: str, *, name: Optional[str] = None, tags: Optional[Sequence[str]] = None,
               folders: Optional[Sequence[str]] = None, annotation: Optional[str] = None,
               url: Optional[str] = None, star: Optional[int] = None, modification_time: Optional[int] = None,
               no_thumbnail: Optional[bool] = None, no_preview: Optional[bool] = None,
               is_deleted: Optional[bool] = None) -> Item:
        """Change some fields of an item; the others stay as they are (``POST /api/v2/item/update``).

        ``tags`` and ``folders`` replace the current lists. ``is_deleted=True`` moves the item
        to the trash and ``False`` restores it.

        Returns:
            The updated item.
        """
        return self._post('update', {
            'id': item_id, 'name': name, 'tags': _list(tags), 'folders': _list(folders), 'annotation': annotation,
            'url': url, 'star': star, 'modificationTime': modification_time, 'noThumbnail': no_thumbnail,
            'noPreview': no_preview, 'isDeleted': is_deleted})

    def set_custom_thumbnail(self, item_id: str, file_path: str) -> Any:
        """Use a local image as the item's thumbnail (``POST /api/v2/item/setCustomThumbnail``).

        Eagle waits up to 10 seconds for the thumbnail before it answers.
        """
        return self._post('setCustomThumbnail', {'itemId': item_id, 'filePath': file_path})

    def refresh_thumbnail(self, item_id: str) -> Any:
        """Regenerate the thumbnail, size, dimensions and palette (``POST /api/v2/item/refreshThumbnail``)."""
        return self._post('refreshThumbnail', {'itemId': item_id})

    def get_comments(self, item_id: str) -> List[Dict[str, Any]]:
        """The comments on an image area or video moment (``GET /api/v2/item/getComments``, Build 22+)."""
        return self._get('getComments', {'id': item_id})

    def add_comment(self, item_id: str, annotation: Optional[str] = None, *, x: Optional[float] = None,
                    y: Optional[float] = None, width: Optional[float] = None, height: Optional[float] = None,
                    duration: Optional[float] = None) -> Any:
        """Comment on an image area (``x``, ``y``, ``width``, ``height``) or a video moment (``duration``).

        ``POST /api/v2/item/addComment``, Eagle 4.0 Build 22 or later.

        Raises:
            ValueError: Neither or both kinds of position were given, or the area is incomplete.
        """
        rect = _compact(x=x, y=y, width=width, height=height)
        if duration is not None and rect:
            raise ValueError('Give either duration (video) or x, y, width and height (image), not both.')
        if duration is None and len(rect) != 4:
            raise ValueError('An image comment needs x, y, width and height; a video comment needs duration.')
        return self._post('addComment', dict(rect, id=item_id, annotation=annotation, duration=duration))

    def update_comment(self, item_id: str, comment_id: str, annotation: Optional[str] = None, *,
                       x: Optional[float] = None, y: Optional[float] = None, width: Optional[float] = None,
                       height: Optional[float] = None, duration: Optional[float] = None) -> Any:
        """Change a comment's text or position (``POST /api/v2/item/updateComment``, Build 22+).

        Image comments can only move their area and video comments only their ``duration``.
        """
        rect = _compact(x=x, y=y, width=width, height=height)
        if duration is not None and rect:
            raise ValueError('A comment is either on an image area or on a video moment, not both.')
        return self._post('updateComment', dict(rect, id=item_id, commentId=comment_id, annotation=annotation,
                                                duration=duration))

    def remove_comment(self, item_id: str, comment_id: str) -> Any:
        """Delete a comment (``POST /api/v2/item/removeComment``, Build 22+)."""
        return self._post('removeComment', {'id': item_id, 'commentId': comment_id})


class FolderAPI(_Section):
    """List, create and organize folders. Docs: https://developer.eagle.cool/web-api/api/folder"""

    _prefix = 'folder'

    def get(self, *, folder_id: Optional[str] = None, folder_ids: Optional[Sequence[str]] = None,
            is_selected: Optional[bool] = None, is_recent: Optional[bool] = None,
            offset: Optional[int] = None, limit: Optional[int] = None) -> Page:
        """List folders (``POST /api/v2/folder/get``); ``is_recent=True`` gives the recently used ones.

        Returns:
            A page: ``{'data': [folder, ...], 'total': int, 'offset': int, 'limit': int}``.
        """
        return self._post('get', {'id': folder_id, 'ids': _list(folder_ids), 'isSelected': is_selected,
                                  'isRecent': is_recent, 'offset': offset, 'limit': limit})

    def iterate(self, page_size: int = 200, offset: int = 0, **filters: Any) -> Iterator[Dict[str, Any]]:
        """Yield every folder matching the filters of :meth:`get`."""
        return _paginate(lambda **page: self.get(**dict(filters, **page)), offset, page_size)

    def create(self, name: str, *, description: Optional[str] = None,
               parent: Optional[str] = None) -> Dict[str, Any]:
        """Create a folder, inside ``parent`` if given (``POST /api/v2/folder/create``).

        Returns:
            The new folder.
        """
        return self._post('create', {'name': name, 'description': description, 'parent': parent})

    def update(self, folder_id: str, *, name: Optional[str] = None, description: Optional[str] = None,
               tags: Optional[Sequence[str]] = None, icon_color: Optional[str] = None,
               parent: Optional[str] = None, move_to_root: bool = False) -> Dict[str, Any]:
        """Change some fields of a folder, or move it (``POST /api/v2/folder/update``).

        Args:
            folder_id: The folder to change.
            name: New name.
            description: New description.
            tags: New folder tags (replaces the current ones).
            icon_color: One of :data:`ICON_COLORS`.
            parent: Move the folder into this folder.
            move_to_root: Move the folder to the top level.

        Returns:
            The updated folder.
        """
        if move_to_root and parent is not None:
            raise ValueError('Give either parent or move_to_root, not both.')
        body = {'id': folder_id, 'name': name, 'description': description, 'tags': _list(tags),
                'iconColor': icon_color, 'parent': parent}
        body = _compact(**body)
        if move_to_root:
            body['parent'] = None  # Eagle's way of saying "top level"
        return self._client.data('POST', self._path('update'), None, body)


class SmartFolderAPI(_Section):
    """Smart folders and the items that match them (Eagle 4.0 Build 22 or later).

    Docs: https://developer.eagle.cool/web-api/api/smart-folder
    """

    _prefix = 'smartFolder'

    def get(self, *, smart_folder_id: Optional[str] = None,
            smart_folder_ids: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
        """All smart folders, or the given ones (``POST /api/v2/smartFolder/get``). Not paginated."""
        return self._post('get', {'id': smart_folder_id, 'ids': _list(smart_folder_ids)})

    def create(self, name: str, conditions: Sequence[Dict[str, Any]], *, description: Optional[str] = None,
               icon: Optional[str] = None, icon_color: Optional[str] = None,
               parent: Optional[str] = None) -> Dict[str, Any]:
        """Create a smart folder (``POST /api/v2/smartFolder/create``).

        ``conditions`` is a list of rule groups, e.g.
        ``[{'rules': [{'property': 'width', 'method': '>', 'value': [1920]}], 'match': 'AND'}]``.
        :meth:`get_rules` lists the properties and methods Eagle accepts.
        """
        return self._post('create', {'name': name, 'conditions': list(conditions), 'description': description,
                                     'icon': icon, 'iconColor': icon_color, 'parent': parent})

    def update(self, smart_folder_id: str, *, name: Optional[str] = None,
               conditions: Optional[Sequence[Dict[str, Any]]] = None, description: Optional[str] = None,
               icon: Optional[str] = None, icon_color: Optional[str] = None) -> Dict[str, Any]:
        """Change some fields of a smart folder (``POST /api/v2/smartFolder/update``)."""
        return self._post('update', {'id': smart_folder_id, 'name': name, 'conditions': _list(conditions),
                                     'description': description, 'icon': icon, 'iconColor': icon_color})

    def remove(self, smart_folder_id: str) -> Any:
        """Delete a smart folder and its child smart folders (``POST /api/v2/smartFolder/remove``)."""
        return self._post('remove', {'id': smart_folder_id})

    def get_items(self, smart_folder_id: str, *, order_by: Optional[str] = None,
                  fields: Optional[Sequence[str]] = None) -> List[Item]:
        """The items that match a smart folder (``POST /api/v2/smartFolder/getItems``)."""
        return self._post('getItems', {'smartFolderId': smart_folder_id, 'orderBy': order_by,
                                       'fields': _list(fields)})

    def get_rules(self) -> Dict[str, Any]:
        """The properties, methods and value types allowed in conditions (``GET /api/v2/smartFolder/getRules``)."""
        return self._get('getRules')


class TagAPI(_Section):
    """List, rename and merge tags. Docs: https://developer.eagle.cool/web-api/api/tag"""

    _prefix = 'tag'

    def get(self, *, name: Optional[str] = None, offset: Optional[int] = None,
            limit: Optional[int] = None) -> Page:
        """List tags, optionally only those whose name contains ``name`` (``POST /api/v2/tag/get``)."""
        return self._post('get', {'name': name, 'offset': offset, 'limit': limit})

    def iterate(self, name: Optional[str] = None, page_size: int = 200, offset: int = 0) -> Iterator[Dict[str, Any]]:
        """Yield every tag (whose name contains ``name``, if given)."""
        return _paginate(lambda **page: self.get(name=name, **page), offset, page_size)

    def get_recent(self, *, offset: Optional[int] = None, limit: Optional[int] = None) -> Page:
        """Recently used tags (``GET /api/v2/tag/getRecentTags``)."""
        return self._get('getRecentTags', {'offset': offset, 'limit': limit})

    def get_starred(self, *, offset: Optional[int] = None, limit: Optional[int] = None) -> Page:
        """Starred (pinned) tags (``GET /api/v2/tag/getStarredTags``)."""
        return self._get('getStarredTags', {'offset': offset, 'limit': limit})

    def rename(self, original_name: str, new_name: str) -> Dict[str, Any]:
        """Rename a tag on every item that has it (``POST /api/v2/tag/update``).

        Returns:
            The renamed tag.
        """
        return self._post('update', {'originalName': original_name, 'name': new_name})

    def merge(self, source: str, target: str) -> Dict[str, Any]:
        """Replace tag ``source`` with ``target`` on every item and delete ``source`` (``POST /api/v2/tag/merge``).

        Returns:
            ``{'affectedItems': int, 'sourceRemoved': bool}``
        """
        return self._post('merge', {'source': source, 'target': target})


class TagGroupAPI(_Section):
    """Create and organize tag groups. Docs: https://developer.eagle.cool/web-api/api/tag-group"""

    _prefix = 'tagGroup'

    def get(self, *, offset: Optional[int] = None, limit: Optional[int] = None) -> Page:
        """List tag groups (``GET /api/v2/tagGroup/get``)."""
        return self._get('get', {'offset': offset, 'limit': limit})

    def create(self, name: str, tags: Sequence[str], *, color: Optional[str] = None,
               description: Optional[str] = None) -> Dict[str, Any]:
        """Create a tag group (``POST /api/v2/tagGroup/create``)."""
        return self._post('create', {'name': name, 'tags': list(tags), 'color': color,
                                     'description': description})

    def update(self, group_id: str, name: str, tags: Sequence[str], *, color: Optional[str] = None,
               description: Optional[str] = None) -> Dict[str, Any]:
        """Replace a tag group's name and tags (``POST /api/v2/tagGroup/update``); Eagle requires both."""
        return self._post('update', {'id': group_id, 'name': name, 'tags': list(tags), 'color': color,
                                     'description': description})

    def remove(self, group_id: str) -> Any:
        """Delete a tag group; its tags stay (``POST /api/v2/tagGroup/remove``)."""
        return self._post('remove', {'id': group_id})

    def add_tags(self, group_id: str, tags: Sequence[str], *,
                 remove_from_source: Optional[bool] = None) -> Dict[str, Any]:
        """Add tags to a group; ``remove_from_source=True`` takes them out of their current groups."""
        return self._post('addTags', {'groupId': group_id, 'tags': list(tags),
                                      'removeFromSource': remove_from_source})

    def remove_tags(self, group_id: str, tags: Sequence[str]) -> Dict[str, Any]:
        """Take tags out of a group; the tags themselves stay (``POST /api/v2/tagGroup/removeTags``)."""
        return self._post('removeTags', {'groupId': group_id, 'tags': list(tags)})


class LibraryAPI(_Section):
    """The open library. Docs: https://developer.eagle.cool/web-api/api/library"""

    _prefix = 'library'

    def info(self) -> Dict[str, Any]:
        """Name, path, folders, smart folders, quick access and tag groups (``GET /api/v2/library/info``)."""
        return self._get('info')

    def history(self, *, offset: Optional[int] = None, limit: Optional[int] = None) -> Page:
        """Recently opened libraries, as a page of ``{'name', 'path'}`` (``GET /api/v2/library/history``)."""
        return self._get('history', {'offset': offset, 'limit': limit})

    def switch(self, library_path: str) -> Any:
        """Open another library (``POST /api/v2/library/switch``)."""
        return self._post('switch', {'libraryPath': library_path})

    def icon(self, library_path: str) -> bytes:
        """A library's icon image (``GET /api/v2/library/icon``)."""
        return self._client.binary(self._path('icon'), {'libraryPath': library_path})


class AppAPI(_Section):
    """The running Eagle app. Docs: https://developer.eagle.cool/web-api/api/app"""

    _prefix = 'app'

    def info(self) -> Dict[str, Any]:
        """``version``, ``prereleaseVersion``, ``buildVersion`` and ``platform`` (``GET /api/v2/app/info``)."""
        return self._get('info')


class AISearchAPI(_Section):
    """Semantic search by text or image; needs Eagle's AI Search plugin.

    Docs: https://developer.eagle.cool/web-api/api/ai-search
    """

    _prefix = 'aiSearch'

    def is_installed(self) -> bool:
        """Whether the AI Search plugin is installed."""
        return self._get('isInstalled')

    def is_ready(self) -> bool:
        """Whether AI Search is ready to search."""
        return self._get('isReady')

    def is_starting(self) -> bool:
        """Whether AI Search is still starting up."""
        return self._get('isStarting')

    def is_syncing(self) -> bool:
        """Whether AI Search is indexing the library."""
        return self._get('isSyncing')

    def get_sync_status(self) -> Dict[str, Any]:
        """Indexing progress: ``isSyncing``, ``syncedCount``, ``totalCount``, ``progress``."""
        return self._get('getSyncStatus')

    def check_service_health(self) -> Dict[str, Any]:
        """Health check of the AI Search service."""
        return self._get('checkServiceHealth')

    def search_by_text(self, query: str, *, limit: Optional[int] = None,
                       options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Find items that match a description, e.g. ``'an orange cat'``.

        Returns:
            ``{'results': [{'item': item, 'score': float}, ...]}``, best match first.
        """
        return self._post('searchByText', {'query': query, 'options': _options(limit, options)})

    def search_by_base64(self, base64: str, *, limit: Optional[int] = None,
                         options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Find items that look like a Base64-encoded image (reverse image search)."""
        return self._post('searchByBase64', {'base64': base64, 'options': _options(limit, options)})

    def search_by_item_id(self, item_id: str, *, limit: Optional[int] = None,
                          options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Find items that look like an item already in the library."""
        return self._post('searchByItemId', {'itemId': item_id, 'options': _options(limit, options)})


def _list(values: Optional[Sequence[Any]]) -> Optional[List[Any]]:
    """A JSON-ready list, so tuples and other sequences work too; ``None`` stays ``None``."""
    if values is None:
        return None
    if isinstance(values, str):
        return [values]
    return list(values)


def _options(limit: Optional[int], options: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    merged = dict(options or {})
    if limit is not None:
        merged['limit'] = limit
    return merged or None


class EagleV2:
    """Eagle's Web API V2 (Eagle 4.0 Build 21 or later), grouped like the official docs.

    Args:
        base_url: Where Eagle listens. Defaults to ``http://localhost:41595``.
        token: API token for calls from another device (Eagle > Preferences > Developer).
            When omitted, the ``EAGLE_API_TOKEN`` environment variable is used if set.
        timeout: Seconds to wait for Eagle. ``None`` (default) waits as long as it takes.
        session: A ``requests.Session`` to send requests with.
        client: An existing :class:`~eaglewrapper.client.EagleClient` to share (used by
            ``Eagle().v2``); the other arguments are then ignored.

    Attributes:
        item, folder, smart_folder, tag, tag_group, library, app, ai_search: The endpoint groups.
    """

    def __init__(self, base_url: str = '{}:{}'.format(DEFAULT_HOST, DEFAULT_PORT), *,
                 token: Optional[str] = None, timeout: Optional[float] = None,
                 session: Optional[requests.Session] = None, client: Optional[EagleClient] = None):
        self._client = client or EagleClient(base_url, token=token, timeout=timeout, session=session)
        self.item = ItemAPI(self._client)
        self.folder = FolderAPI(self._client)
        self.smart_folder = SmartFolderAPI(self._client)
        self.tag = TagAPI(self._client)
        self.tag_group = TagGroupAPI(self._client)
        self.library = LibraryAPI(self._client)
        self.app = AppAPI(self._client)
        self.ai_search = AISearchAPI(self._client)

    def __repr__(self) -> str:
        return 'EagleV2({!r})'.format(self._client.base_url)

    def request(self, method: str, path: str, *, params: Params = None, body: Any = None) -> Any:
        """Call any endpoint directly, e.g. one added to Eagle after this release.

        Args:
            method: ``'GET'`` or ``'POST'``.
            path: ``'item/get'`` (relative to ``/api/v2/``) or a full path like ``'/api/v2/item/get'``.
            params: Query parameters.
            body: JSON body for POST.

        Returns:
            The ``data`` of Eagle's reply.
        """
        method = method.upper()
        if method not in ('GET', 'POST'):
            raise ValueError("method must be 'GET' or 'POST', not {!r}".format(method))
        if api_for_path(path) is None:
            path = API_V2.path(path)
        if method == 'POST' and body is None:
            body = {}
        return self._client.data(method, path, params, body)
