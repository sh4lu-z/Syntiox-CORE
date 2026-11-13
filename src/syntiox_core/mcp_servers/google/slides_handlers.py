import io
import os
import json
import uuid
from mcp.server.fastmcp import FastMCP
from googleapiclient.http import MediaIoBaseDownload
from google_common import get_service

mcp = FastMCP("Google-Slides-Tools")


def _slides():
    return get_service("slides", "v1")


def _drive():
    return get_service("drive", "v3")


@mcp.tool()
def slides_content(
    action: str,
    presentation_id: str = "",
    slide_object_id: str = "",
    slide_title: str = "",
    slide_body: str = "",
    image_url: str = "",
    bullets_json: str = "",
    find_text: str = "",
    replace_text: str = "",
    new_index: int = 0,
    color_hex: str = "#FFFFFF",
) -> str:
    """Manage Google Slides content: read_text, add_slide, add_image_slide, add_bullet_slide, update_text, delete_slide, duplicate_slide, reorder_slide, set_background."""
    action_clean = (action or "").strip().lower()
    pid = presentation_id.strip()

    try:
        svc = _slides()

        if action_clean in ("read_text", "get_text"):
            if not pid:
                return "Error: 'presentation_id' is required."
            pres = svc.presentations().get(presentationId=pid).execute()
            lines = [f"PRESENTATION TEXT: {pres.get('title')}", "=" * 40]
            for i, slide in enumerate(pres.get("slides", []), 1):
                texts = []
                for elem in slide.get("pageElements", []):
                    for te in elem.get("shape", {}).get("text", {}).get("textElements", []):
                        c = te.get("textRun", {}).get("content", "").strip()
                        if c:
                            texts.append(c)
                lines.append(f"\nSLIDE {i} (ID: {slide.get('objectId')}):")
                lines.append("\n".join(texts) if texts else "(empty)")
            return "\n".join(lines)

        elif action_clean in ("add_slide", "add_text_slide"):
            if not pid:
                return "Error: 'presentation_id' is required."
            slide_id = f"slide_{uuid.uuid4().hex[:8]}"
            title_id = f"title_{uuid.uuid4().hex[:8]}"
            body_id = f"body_{uuid.uuid4().hex[:8]}"
            reqs = [
                {"addSlide": {"objectId": slide_id, "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
                {"createShape": {"objectId": title_id, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": slide_id, "size": {"width": {"magnitude": 550, "unit": "PT"}, "height": {"magnitude": 60, "unit": "PT"}}, "transform": {"scaleX": 1, "scaleY": 1, "translateX": 30, "translateY": 30, "unit": "PT"}}}},
                {"insertText": {"objectId": title_id, "insertionIndex": 0, "text": slide_title or "Untitled"}},
                {"createShape": {"objectId": body_id, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": slide_id, "size": {"width": {"magnitude": 550, "unit": "PT"}, "height": {"magnitude": 280, "unit": "PT"}}, "transform": {"scaleX": 1, "scaleY": 1, "translateX": 30, "translateY": 110, "unit": "PT"}}}},
                {"insertText": {"objectId": body_id, "insertionIndex": 0, "text": slide_body or ""}},
            ]
            svc.presentations().batchUpdate(presentationId=pid, body={"requests": reqs}).execute()
            return f"Slide added. Slide ID: {slide_id}"

        elif action_clean == "add_image_slide":
            if not pid or not image_url:
                return "Error: 'presentation_id' and 'image_url' are required."
            slide_id = f"slide_{uuid.uuid4().hex[:8]}"
            img_id = f"img_{uuid.uuid4().hex[:8]}"
            reqs = [
                {"addSlide": {"objectId": slide_id, "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
                {"createImage": {"objectId": img_id, "url": image_url, "elementProperties": {"pageObjectId": slide_id, "size": {"width": {"magnitude": 400, "unit": "PT"}, "height": {"magnitude": 300, "unit": "PT"}}, "transform": {"scaleX": 1, "scaleY": 1, "translateX": 50, "translateY": 50, "unit": "PT"}}}},
            ]
            svc.presentations().batchUpdate(presentationId=pid, body={"requests": reqs}).execute()
            return f"Image slide added. Slide ID: {slide_id}"

        elif action_clean == "add_bullet_slide":
            if not pid:
                return "Error: 'presentation_id' is required."
            bullets_list = json.loads(bullets_json) if bullets_json else []
            body_text = "\n".join(f"- {b}" for b in bullets_list) if isinstance(bullets_list, list) else bullets_json
            return slides_content(action="add_slide", presentation_id=pid, slide_title=slide_title, slide_body=body_text)

        elif action_clean in ("update_text", "replace_text"):
            if not pid or not find_text:
                return "Error: 'presentation_id' and 'find_text' are required."
            res = svc.presentations().batchUpdate(
                presentationId=pid,
                body={"requests": [{"replaceAllText": {"containsText": {"text": find_text, "matchCase": False}, "replaceText": replace_text or ""}}]}
            ).execute()
            count = res.get("replies", [{}])[0].get("replaceAllText", {}).get("occurrencesChanged", 0)
            return f"Updated {count} text occurrence(s) in presentation {pid}."

        elif action_clean == "delete_slide":
            if not pid or not slide_object_id:
                return "Error: 'presentation_id' and 'slide_object_id' are required."
            svc.presentations().batchUpdate(
                presentationId=pid, body={"requests": [{"deleteObject": {"objectId": slide_object_id.strip()}}]}
            ).execute()
            return f"Slide {slide_object_id} deleted."

        elif action_clean == "duplicate_slide":
            if not pid or not slide_object_id:
                return "Error: 'presentation_id' and 'slide_object_id' are required."
            res = svc.presentations().batchUpdate(
                presentationId=pid, body={"requests": [{"duplicateObject": {"objectId": slide_object_id.strip()}}]}
            ).execute()
            new_id = res["replies"][0]["duplicateObject"]["objectId"]
            return f"Slide duplicated. New Slide ID: {new_id}"

        elif action_clean == "reorder_slide":
            if not pid or not slide_object_id:
                return "Error: 'presentation_id' and 'slide_object_id' are required."
            svc.presentations().batchUpdate(
                presentationId=pid,
                body={"requests": [{"updateSlidesPosition": {"slideObjectIds": [slide_object_id.strip()], "insertionIndex": new_index}}]}
            ).execute()
            return f"Slide {slide_object_id} moved to index {new_index}."

        elif action_clean == "set_background":
            if not pid or not slide_object_id:
                return "Error: 'presentation_id' and 'slide_object_id' are required."
            hex_c = color_hex.strip()
            if not hex_c.startswith("#") or len(hex_c) != 7:
                return "Error: 'color_hex' must be in format #RRGGBB."
            r = int(hex_c[1:3], 16) / 255.0
            g = int(hex_c[3:5], 16) / 255.0
            b = int(hex_c[5:7], 16) / 255.0
            svc.presentations().batchUpdate(
                presentationId=pid,
                body={"requests": [{"updatePageProperties": {"objectId": slide_object_id.strip(), "pageProperties": {"pageBackgroundFill": {"solidFill": {"color": {"rgbColor": {"red": r, "green": g, "blue": b}}}}}, "fields": "pageBackgroundFill"}}]}
            ).execute()
            return f"Background color for slide {slide_object_id} set to {color_hex}."

        else:
            return f"Unknown slide content action '{action}'. Valid actions: read_text, add_slide, add_image_slide, add_bullet_slide, update_text, delete_slide, duplicate_slide, reorder_slide, set_background."

    except Exception as e:
        return f"Slide content operation failed: {e}"


@mcp.tool()
def slides_manage(
    action: str,
    presentation_id: str = "",
    title: str = "",
    local_path: str = "",
    export_format: str = "pdf",
    max_results: int = 10,
) -> str:
    """Manage Google Slides presentations lifecycle: list_presentations, get_info, create_presentation, delete_presentation, export_presentation."""
    action_clean = (action or "").strip().lower()
    pid = presentation_id.strip()

    try:
        drive_svc = _drive()
        svc = _slides()

        if action_clean in ("list_presentations", "list"):
            res = drive_svc.files().list(
                q="mimeType='application/vnd.google-apps.presentation' and trashed=false",
                pageSize=max_results, fields="files(id, name, modifiedTime, webViewLink)"
            ).execute()
            files = res.get("files", [])
            if not files:
                return "No presentations found."
            lines = [f"SLIDES PRESENTATIONS - {len(files)} FOUND", "-" * 40]
            for f in files:
                lines.append(f"Title: {f['name']} | ID: {f['id']} | Link: {f.get('webViewLink')}")
            return "\n".join(lines)

        elif action_clean in ("get_info", "info"):
            if not pid:
                return "Error: 'presentation_id' is required."
            pres = svc.presentations().get(presentationId=pid).execute()
            slides = pres.get("slides", [])
            lines = [
                f"Presentation: '{pres.get('title')}' - {len(slides)} slides",
                f"Link: https://docs.google.com/presentation/d/{pid}/edit",
                "-" * 40,
            ]
            for i, s in enumerate(slides, 1):
                lines.append(f"  Slide {i} (ID: {s.get('objectId')})")
            return "\n".join(lines)

        elif action_clean in ("create_presentation", "create"):
            pres_title = title or "Untitled Presentation"
            res = svc.presentations().create(body={"title": pres_title}).execute()
            new_id = res["presentationId"]
            return f"Presentation created: '{pres_title}'. ID: {new_id} Link: https://docs.google.com/presentation/d/{new_id}/edit"

        elif action_clean in ("delete_presentation", "delete"):
            if not pid:
                return "Error: 'presentation_id' is required."
            drive_svc.files().delete(fileId=pid).execute()
            return f"Presentation {pid} deleted."

        elif action_clean == "export_presentation":
            if not pid or not local_path:
                return "Error: 'presentation_id' and 'local_path' are required."
            mime_map = {
                "pdf": "application/pdf",
                "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            }
            mime = mime_map.get(export_format.lower(), "application/pdf")
            parent = os.path.dirname(os.path.abspath(local_path))
            if parent and not os.path.isdir(parent):
                return f"Error: Destination directory does not exist: {parent}"
            req = drive_svc.files().export_media(fileId=pid, mimeType=mime)
            with io.FileIO(local_path, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, req)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            return f"Exported presentation to {local_path} ({export_format})."

        else:
            return f"Unknown presentation management action '{action}'. Valid actions: list_presentations, get_info, create_presentation, delete_presentation, export_presentation."

    except Exception as e:
        return f"Presentation management operation failed: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
