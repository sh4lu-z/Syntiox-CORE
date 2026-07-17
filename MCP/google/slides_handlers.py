"""
🎨 Google Slides Handler Tools
"""
import io
import os
import uuid
from mcp.server.fastmcp import FastMCP
from googleapiclient.http import MediaIoBaseDownload
from google_common import get_service, share_file

mcp = FastMCP("Google-Slides-Tools")


def _slides():
    return get_service('slides', 'v1')


def _drive():
    return get_service('drive', 'v3')


@mcp.tool()
def list_presentations(max_results: int = 10) -> str:
    """List Google Slides presentations in Drive."""
    try:
        results = _drive().files().list(
            q="mimeType='application/vnd.google-apps.presentation' and trashed=false",
            pageSize=max_results,
            fields="files(id, name, modifiedTime, webViewLink)"
        ).execute()
        files = results.get('files', [])
        if not files:
            return "🎨 No presentations found."
        output = f"🎨 SLIDES — {len(files)}\n{'─'*40}\n"
        for f in files:
            output += f"🖼️ {f['name']} | ID: {f['id']}\n"
        return output
    except Exception as e:
        return f"❌ Error listing presentations: {e}"


@mcp.tool()
def get_presentation_info(presentation_id: str) -> str:
    """Get presentation info and slide preview."""
    presentation_id = presentation_id.strip()
    try:
        pres = _slides().presentations().get(presentationId=presentation_id).execute()
        slides = pres.get('slides', [])
        output = (
            f"🎨 {pres.get('title')} — {len(slides)} slides\n"
            f"🔗 https://docs.google.com/presentation/d/{presentation_id}/edit\n{'─'*40}\n"
        )
        for i, slide in enumerate(slides, 1):
            texts = []
            for elem in slide.get('pageElements', []):
                for te in elem.get('shape', {}).get('text', {}).get('textElements', []):
                    t = te.get('textRun', {}).get('content', '').strip()
                    if t:
                        texts.append(t)
            output += f"  Slide {i} (ID: {slide.get('objectId')}): {' | '.join(texts)[:80]}\n"
        return output
    except Exception as e:
        return f"❌ Error getting presentation info: {e}"


@mcp.tool()
def create_presentation(title: str) -> str:
    """Create a new Google Slides presentation."""
    try:
        result = _slides().presentations().create(body={'title': title}).execute()
        pid = result['presentationId']
        return (
            f"✅ Presentation '{title}' created.\n"
            f"   🔑 ID: {pid}\n"
            f"   💡 Use ID for add/update/delete slides."
        )
    except Exception as e:
        return f"❌ Error creating presentation: {e}"


@mcp.tool()
def add_text_slide(presentation_id: str, slide_title: str, slide_body: str) -> str:
    """Add a text slide (title + body) to a presentation."""
    presentation_id = presentation_id.strip()
    try:
        slide_id = f"slide_{uuid.uuid4().hex[:8]}"
        title_id = f"title_{uuid.uuid4().hex[:8]}"
        body_id = f"body_{uuid.uuid4().hex[:8]}"
        requests = [
            {'addSlide': {'objectId': slide_id, 'slideLayoutReference': {'predefinedLayout': 'BLANK'}}},
            {
                'createShape': {
                    'objectId': title_id, 'shapeType': 'TEXT_BOX',
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {'width': {'magnitude': 550, 'unit': 'PT'}, 'height': {'magnitude': 60, 'unit': 'PT'}},
                        'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 30, 'translateY': 30, 'unit': 'PT'},
                    },
                }
            },
            {'insertText': {'objectId': title_id, 'insertionIndex': 0, 'text': slide_title}},
            {
                'createShape': {
                    'objectId': body_id, 'shapeType': 'TEXT_BOX',
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {'width': {'magnitude': 550, 'unit': 'PT'}, 'height': {'magnitude': 280, 'unit': 'PT'}},
                        'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 30, 'translateY': 110, 'unit': 'PT'},
                    },
                }
            },
            {'insertText': {'objectId': body_id, 'insertionIndex': 0, 'text': slide_body}},
        ]
        _slides().presentations().batchUpdate(
            presentationId=presentation_id, body={'requests': requests}
        ).execute()
        return f"✅ Slide added (slideId: {slide_id})."
    except Exception as e:
        return f"❌ Error adding slide: {e}"


@mcp.tool()
def get_slides_text(presentation_id: str) -> str:
    """Extract all text from a presentation."""
    presentation_id = presentation_id.strip()
    try:
        pres = _slides().presentations().get(presentationId=presentation_id).execute()
        output = f"🎨 '{pres.get('title')}' — TEXT\n{'═'*40}\n"
        for i, slide in enumerate(pres.get('slides', []), 1):
            texts = []
            for elem in slide.get('pageElements', []):
                for te in elem.get('shape', {}).get('text', {}).get('textElements', []):
                    c = te.get('textRun', {}).get('content', '').strip()
                    if c:
                        texts.append(c)
            output += f"\nSLIDE {i}:\n" + ('\n'.join(texts) if texts else '(empty)') + '\n'
        return output
    except Exception as e:
        return f"❌ Error getting slides text: {e}"


@mcp.tool()
def update_slide_text(presentation_id: str, find_text: str, replace_text: str) -> str:
    """Replace specific text across a presentation."""
    presentation_id = presentation_id.strip()
    try:
        result = _slides().presentations().batchUpdate(
            presentationId=presentation_id,
            body={'requests': [{
                'replaceAllText': {
                    'containsText': {'text': find_text, 'matchCase': False},
                    'replaceText': replace_text,
                }
            }]}
        ).execute()
        count = result.get('replies', [{}])[0].get('replaceAllText', {}).get('occurrencesChanged', 0)
        return f"✅ Updated {count} text occurrence(s)."
    except Exception as e:
        return f"❌ Error updating slide text: {e}"


@mcp.tool()
def replace_text_in_presentation(presentation_id: str, find_text: str, replace_text: str) -> str:
    """Find and replace text in a presentation."""
    return update_slide_text(presentation_id, find_text, replace_text)


@mcp.tool()
def delete_slide(presentation_id: str, slide_object_id: str) -> str:
    """Delete a slide by objectId."""
    presentation_id = presentation_id.strip()
    try:
        _slides().presentations().batchUpdate(
            presentationId=presentation_id,
            body={'requests': [{'deleteObject': {'objectId': slide_object_id}}]}
        ).execute()
        return f"🗑️ Slide {slide_object_id} deleted."
    except Exception as e:
        return f"❌ Error deleting slide: {e}"


@mcp.tool()
def duplicate_slide(presentation_id: str, slide_object_id: str) -> str:
    """Duplicate a slide."""
    presentation_id = presentation_id.strip()
    try:
        result = _slides().presentations().batchUpdate(
            presentationId=presentation_id,
            body={'requests': [{'duplicateObject': {'objectId': slide_object_id}}]}
        ).execute()
        new_id = result['replies'][0]['duplicateObject']['objectId']
        return f"✅ Slide duplicated. New ID: {new_id}"
    except Exception as e:
        return f"❌ Error duplicating slide: {e}"


@mcp.tool()
def reorder_slide(presentation_id: str, slide_object_id: str, new_index: int) -> str:
    """Reorder a slide to a new index."""
    presentation_id = presentation_id.strip()
    try:
        _slides().presentations().batchUpdate(
            presentationId=presentation_id,
            body={'requests': [{
                'updateSlidesPosition': {
                    'slideObjectIds': [slide_object_id],
                    'insertionIndex': new_index,
                }
            }]}
        ).execute()
        return f"✅ Slide moved to index {new_index}."
    except Exception as e:
        return f"❌ Error reordering slide: {e}"


@mcp.tool()
def delete_presentation(presentation_id: str) -> str:
    """Delete a Google Slides presentation."""
    presentation_id = presentation_id.strip()
    try:
        _drive().files().delete(fileId=presentation_id).execute()
        return f"🗑️ Presentation deleted (ID: {presentation_id})."
    except Exception as e:
        return f"❌ Error deleting presentation: {e}"


@mcp.tool()
def add_image_slide(presentation_id: str, image_url: str, slide_index: int = -1) -> str:
    """Add a blank slide with an image from a URL."""
    presentation_id = presentation_id.strip()
    try:
        slide_id = f"slide_{uuid.uuid4().hex[:8]}"
        img_id = f"img_{uuid.uuid4().hex[:8]}"
        requests = [
            {'addSlide': {'objectId': slide_id, 'slideLayoutReference': {'predefinedLayout': 'BLANK'}}},
            {
                'createImage': {
                    'objectId': img_id,
                    'url': image_url,
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {'width': {'magnitude': 400, 'unit': 'PT'}, 'height': {'magnitude': 300, 'unit': 'PT'}},
                        'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 50, 'translateY': 50, 'unit': 'PT'},
                    },
                }
            },
        ]
        _slides().presentations().batchUpdate(
            presentationId=presentation_id, body={'requests': requests}
        ).execute()
        return f"✅ Image slide added (slideId: {slide_id})."
    except Exception as e:
        return f"❌ Error adding image slide: {e}"


@mcp.tool()
def add_bullet_slide(presentation_id: str, title: str, bullets_json: str) -> str:
    """Add a slide with a bulleted list. bullets_json must be a JSON array."""
    presentation_id = presentation_id.strip()
    try:
        import json
        bullets_list = json.loads(bullets_json)
        if not isinstance(bullets_list, list): return "❌ bullets_json must be a JSON array."
        bullets = [str(b).strip() for b in bullets_list if str(b).strip()]
        body = '\n'.join(f"• {b}" for b in bullets)
        return add_text_slide(presentation_id, title, body)
    except Exception as e:
        return f"❌ Error adding bullet slide: {e}"


@mcp.tool()
def update_slide_background(presentation_id: str, slide_object_id: str, color_hex: str) -> str:
    """Set the background color of a slide."""
    presentation_id = presentation_id.strip()
    try:
        if not color_hex.startswith('#') or len(color_hex) != 7:
            return "❌ color_hex must be #RRGGBB."
        r = int(color_hex[1:3], 16) / 255
        g = int(color_hex[3:5], 16) / 255
        b = int(color_hex[5:7], 16) / 255
        _slides().presentations().batchUpdate(
            presentationId=presentation_id,
            body={'requests': [{
                'updatePageProperties': {
                    'objectId': slide_object_id,
                    'pageProperties': {
                        'pageBackgroundFill': {
                            'solidFill': {'color': {'rgbColor': {'red': r, 'green': g, 'blue': b}}}
                        }
                    },
                    'fields': 'pageBackgroundFill',
                }
            }]}
        ).execute()
        return f"✅ Background set to {color_hex}."
    except Exception as e:
        return f"❌ Error updating background: {e}"


@mcp.tool()
def export_presentation(presentation_id: str, local_path: str, export_format: str = "pdf") -> str:
    """Export a presentation to PDF or PPTX."""
    presentation_id = presentation_id.strip()
    try:
        mime_map = {
            'pdf': 'application/pdf',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        }
        mime = mime_map.get(export_format.lower())
        if not mime:
            return "❌ export_format: pdf or pptx."
        parent = os.path.dirname(os.path.abspath(local_path))
        if parent and not os.path.isdir(parent):
            return f"❌ Directory not found: {parent}"
        request = _drive().files().export_media(fileId=presentation_id, mimeType=mime)
        fh = io.FileIO(local_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.close()
        return f"✅ Exported to {local_path}."
    except Exception as e:
        return f"❌ Error exporting presentation: {e}"


@mcp.tool()
def share_presentation(presentation_id: str, email: str, role: str = "reader") -> str:
    """Share a presentation via email."""
    presentation_id = presentation_id.strip()
    try:
        perm = share_file(presentation_id, email, role)
        return f"✅ Shared with {perm.get('emailAddress', email)}."
    except Exception as e:
        return f"❌ Error sharing presentation: {e}"


if __name__ == "__main__":
    mcp.run(transport='stdio')
