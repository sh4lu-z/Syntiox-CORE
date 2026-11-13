import json
import uuid
from mcp.server.fastmcp import FastMCP
from google_common import get_service

mcp = FastMCP("Google-Forms-Tools")


def _forms():
    return get_service("forms", "v1")


def _drive():
    return get_service("drive", "v3")


@mcp.tool()
def forms_manage(
    action: str,
    form_id: str = "",
    title: str = "",
    description: str = "",
    question_title: str = "",
    question_type: str = "text",
    options_json: str = "",
    required: bool = False,
    item_id: str = "",
    new_index: int = 0,
    max_results: int = 10,
) -> str:
    """Manage Google Forms lifecycle and questions: list_forms, create_form, get_form_info, update_form_info, delete_form, duplicate_form, get_responder_url, add_question, delete_question, reorder_question."""
    action_clean = (action or "").strip().lower()
    fid = form_id.strip()

    try:
        svc = _forms()
        drive_svc = _drive()

        if action_clean in ("list_forms", "list"):
            res = drive_svc.files().list(
                q="mimeType='application/vnd.google-apps.form' and trashed=false",
                pageSize=max_results, fields="files(id, name, modifiedTime, webViewLink)"
            ).execute()
            files = res.get("files", [])
            if not files:
                return "No Forms found."
            lines = [f"GOOGLE FORMS - {len(files)} FOUND", "-" * 40]
            for f in files:
                lines.append(f"Title: {f['name']} | ID: {f['id']} | Link: {f.get('webViewLink')}")
            return "\n".join(lines)

        elif action_clean in ("create_form", "create"):
            f_title = title or "Untitled Form"
            body = {"info": {"title": f_title}}
            if description:
                body["info"]["description"] = description
            form = svc.forms().create(body=body).execute()
            new_id = form["formId"]
            return f"Form created: '{f_title}'. ID: {new_id} Link: https://docs.google.com/forms/d/{new_id}/edit Responder: {form.get('responderUri', '')}"

        elif action_clean in ("get_form_info", "get_info", "info"):
            if not fid:
                return "Error: 'form_id' is required."
            form = svc.forms().get(formId=fid).execute()
            info = form.get("info", {})
            items = form.get("items", [])
            lines = [
                f"FORM: {info.get('title')}",
                f"Description: {info.get('description', '')}",
                f"Questions Count: {len(items)}",
                f"Edit Link: https://docs.google.com/forms/d/{fid}/edit",
                f"Responder URL: {form.get('responderUri', 'N/A')}",
                "-" * 40,
            ]
            for i, it in enumerate(items, 1):
                qid = it.get("questionItem", {}).get("question", {}).get("questionId", "")
                lines.append(f"  {i}. {it.get('title', '?')} (itemId: {it.get('itemId', '')}, questionId: {qid})")
            return "\n".join(lines)

        elif action_clean in ("update_form_info", "update_info"):
            if not fid:
                return "Error: 'form_id' is required."
            info = {}
            if title:
                info["title"] = title
            if description:
                info["description"] = description
            if not info:
                return "Error: Provide title and/or description to update."
            svc.forms().batchUpdate(
                formId=fid,
                body={"requests": [{"updateFormInfo": {"info": info, "updateMask": ",".join(info.keys())}}]}
            ).execute()
            return f"Form info updated for form {fid}."

        elif action_clean in ("delete_form", "delete"):
            if not fid:
                return "Error: 'form_id' is required."
            drive_svc.files().delete(fileId=fid).execute()
            return f"Form {fid} deleted."

        elif action_clean == "duplicate_form":
            if not fid:
                return "Error: 'form_id' is required."
            res = drive_svc.files().copy(fileId=fid, body={"name": title or "Copy of Form"}).execute()
            return f"Form copied as '{title or 'Copy of Form'}'. ID: {res['id']}"

        elif action_clean == "get_responder_url":
            if not fid:
                return "Error: 'form_id' is required."
            form = svc.forms().get(formId=fid).execute()
            url = form.get("responderUri", f"https://docs.google.com/forms/d/{fid}/viewform")
            return f"Responder URL: {url}"

        elif action_clean == "add_question":
            if not fid or not question_title:
                return "Error: 'form_id' and 'question_title' are required."
            q_id = f"item_{uuid.uuid4().hex[:8]}"
            q_type = question_type.lower()

            if q_type in ("multiple_choice", "radio"):
                opts = json.loads(options_json) if options_json else ["Option 1", "Option 2"]
                options_list = [{"value": str(o).strip()} for o in opts if str(o).strip()]
                q_def = {"required": required, "choiceQuestion": {"type": "RADIO", "options": options_list}}
            elif q_type in ("checkbox", "checkboxes"):
                opts = json.loads(options_json) if options_json else ["Option 1", "Option 2"]
                options_list = [{"value": str(o).strip()} for o in opts if str(o).strip()]
                q_def = {"required": required, "choiceQuestion": {"type": "CHECKBOX", "options": options_list}}
            else:
                is_paragraph = q_type == "paragraph"
                q_def = {"required": required, "textQuestion": {"paragraph": is_paragraph}}

            req = {
                "createItem": {
                    "item": {"itemId": q_id, "title": question_title, "questionItem": {"question": q_def}},
                    "location": {"index": new_index},
                }
            }
            svc.forms().batchUpdate(formId=fid, body={"requests": [req]}).execute()
            return f"Question '{question_title}' ({q_type}) added to form {fid}. Item ID: {q_id}"

        elif action_clean == "delete_question":
            if not fid or not item_id:
                return "Error: 'form_id' and 'item_id' are required."
            svc.forms().batchUpdate(
                formId=fid, body={"requests": [{"deleteItem": {"location": {"index": new_index}} if not item_id else {"deleteItem": {"itemId": item_id}}}]}
            ).execute()
            return f"Question {item_id} deleted from form {fid}."

        elif action_clean == "reorder_question":
            if not fid or not item_id:
                return "Error: 'form_id' and 'item_id' are required."
            svc.forms().batchUpdate(
                formId=fid,
                body={"requests": [{"updateItemLocation": {"location": {"index": new_index}, "itemId": item_id}}]}
            ).execute()
            return f"Question {item_id} moved to index {new_index} in form {fid}."

        else:
            return f"Unknown form management action '{action}'. Valid actions: list_forms, create_form, get_form_info, update_form_info, delete_form, duplicate_form, get_responder_url, add_question, delete_question, reorder_question."

    except Exception as e:
        return f"Form management operation failed: {e}"


@mcp.tool()
def forms_responses(
    action: str,
    form_id: str = "",
    response_id: str = "",
    max_responses: int = 20,
) -> str:
    """Manage Google Form responses: list_responses, get_response, clear_responses, summarize_responses."""
    action_clean = (action or "").strip().lower()
    fid = form_id.strip()

    try:
        svc = _forms()

        if action_clean in ("list_responses", "list"):
            if not fid:
                return "Error: 'form_id' is required."
            res = svc.forms().responses().list(formId=fid, pageSize=max_responses).execute()
            responses = res.get("responses", [])
            if not responses:
                return f"No responses found for form {fid}."

            form = svc.forms().get(formId=fid).execute()
            q_map = {}
            for item in form.get("items", []):
                if "questionItem" in item:
                    qid = item["questionItem"]["question"]["questionId"]
                    q_map[qid] = item.get("title", qid)

            lines = [f"RESPONSES ({len(responses)}) FOR FORM {fid}", "=" * 40]
            for i, r in enumerate(responses, 1):
                lines.append(f"\nResponse #{i} (ID: {r.get('responseId')}, Submitted: {r.get('lastSubmittedTime', '')}):")
                for qid, ans in r.get("answers", {}).items():
                    vals = [v.get("value", "") for v in ans.get("textAnswers", {}).get("answers", [])]
                    lines.append(f"  {q_map.get(qid, qid)}: {', '.join(vals)}")
            return "\n".join(lines)

        elif action_clean in ("get_response", "get"):
            if not fid or not response_id:
                return "Error: 'form_id' and 'response_id' are required."
            resp = svc.forms().responses().get(formId=fid, responseId=response_id.strip()).execute()
            lines = [f"RESPONSE DETAILS: {response_id}", "-" * 30]
            for qid, ans in resp.get("answers", {}).items():
                vals = [v.get("value", "") for v in ans.get("textAnswers", {}).get("answers", [])]
                lines.append(f"  Question {qid}: {', '.join(vals)}")
            return "\n".join(lines)

        elif action_clean == "clear_responses":
            if not fid:
                return "Error: 'form_id' is required."
            res = svc.forms().responses().list(formId=fid).execute().get("responses", [])
            if not res:
                return "No responses to clear."
            for r in res:
                svc.forms().responses().delete(formId=fid, responseId=r["responseId"]).execute()
            return f"Cleared {len(res)} response(s) from form {fid}."

        elif action_clean == "summarize_responses":
            if not fid:
                return "Error: 'form_id' is required."
            res = svc.forms().responses().list(formId=fid, pageSize=100).execute()
            responses = res.get("responses", [])
            return f"Total responses count for form {fid}: {len(responses)}"

        else:
            return f"Unknown response action '{action}'. Valid actions: list_responses, get_response, clear_responses, summarize_responses."

    except Exception as e:
        return f"Form responses operation failed: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
