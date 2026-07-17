"""
📋 Google Forms Handler Tools
"""
import uuid
from mcp.server.fastmcp import FastMCP
from google_common import get_service

mcp = FastMCP("Google-Forms-Tools")


def _forms():
    return get_service('forms', 'v1')


def _drive():
    return get_service('drive', 'v3')


@mcp.tool()
def list_forms(max_results: int = 10) -> str:
    """List Google Forms in Drive."""
    try:
        results = _drive().files().list(
            q="mimeType='application/vnd.google-apps.form' and trashed=false",
            pageSize=max_results,
            fields="files(id, name, modifiedTime, webViewLink)"
        ).execute()
        files = results.get('files', [])
        if not files:
            return "📋 No Forms found."
        output = f"📋 GOOGLE FORMS — {len(files)}\n{'─'*40}\n"
        for f in files:
            output += f"📝 {f['name']} | ID: {f['id']}\n"
        return output
    except Exception as e:
        return f"❌ Error listing forms: {e}"


@mcp.tool()
def create_form(title: str, description: str = "") -> str:
    """Create a new Google Form."""
    try:
        body = {'info': {'title': title}}
        if description:
            body['info']['description'] = description
        form = _forms().forms().create(body=body).execute()
        fid = form['formId']
        return (
            f"✅ Form '{title}' created.\n"
            f"   🔑 ID: {fid}\n"
            f"   📤 {form.get('responderUri', '')}\n"
            f"   💡 Use ID to add questions / read responses."
        )
    except Exception as e:
        return f"❌ Error creating form: {e}"


@mcp.tool()
def get_form_info(form_id: str) -> str:
    """Get Form details and questions."""
    form_id = form_id.strip()
    try:
        form = _forms().forms().get(formId=form_id).execute()
        info = form.get('info', {})
        items = form.get('items', [])
        output = (
            f"📋 FORM: {info.get('title')}\n"
            f"Questions: {len(items)}\n"
            f"Edit: https://docs.google.com/forms/d/{form_id}/edit\n"
            f"Share: {form.get('responderUri', 'N/A')}\n{'─'*40}\n"
        )
        for i, item in enumerate(items, 1):
            qid = item.get('questionItem', {}).get('question', {}).get('questionId', '')
            output += f"  {i}. {item.get('title', '?')} (itemId: {item.get('itemId', '')}, qId: {qid})\n"
        return output
    except Exception as e:
        return f"❌ Error getting form info: {e}"


@mcp.tool()
def get_form_responses(form_id: str, max_responses: int = 10) -> str:
    """Get Form responses."""
    form_id = form_id.strip()
    try:
        svc = _forms()
        result = svc.forms().responses().list(formId=form_id, pageSize=max_responses).execute()
        responses = result.get('responses', [])
        if not responses:
            return f"📋 No responses for form {form_id}."
        form = svc.forms().get(formId=form_id).execute()
        q_map = {}
        for item in form.get('items', []):
            if 'questionItem' in item:
                qid = item['questionItem']['question']['questionId']
                q_map[qid] = item.get('title', qid)
        output = f"📊 RESPONSES ({len(responses)})\n{'═'*40}\n"
        for i, resp in enumerate(responses, 1):
            output += f"\n🔹 Response {i}\n"
            for qid, ans in resp.get('answers', {}).items():
                vals = [v.get('value', '') for v in ans.get('textAnswers', {}).get('answers', [])]
                output += f"  ❓ {q_map.get(qid, qid)}: {', '.join(vals)}\n"
        return output
    except Exception as e:
        return f"❌ Error getting form responses: {e}"


@mcp.tool()
def add_text_question(form_id: str, question_title: str, required: bool = False) -> str:
    """Add a text question to a Form."""
    form_id = form_id.strip()
    try:
        item_id = f"item_{uuid.uuid4().hex[:8]}"
        _forms().forms().batchUpdate(
            formId=form_id,
            body={'requests': [{
                'createItem': {
                    'item': {
                        'itemId': item_id,
                        'title': question_title,
                        'questionItem': {
                            'question': {
                                'required': required,
                                'textQuestion': {'paragraph': False},
                            }
                        },
                    },
                    'location': {'index': 0},
                }
            }]}
        ).execute()
        return f"✅ Text question added: '{question_title}' (itemId: {item_id})."
    except Exception as e:
        return f"❌ Error adding text question: {e}"


@mcp.tool()
def add_multiple_choice_question(
    form_id: str, question_title: str, options_json: str, required: bool = False
) -> str:
    """Add a multiple choice question to a Form. options_json must be a JSON array."""
    form_id = form_id.strip()
    try:
        import json
        opts = json.loads(options_json)
        if not isinstance(opts, list): return "❌ options_json must be a JSON array."
        options = [{'value': str(o).strip()} for o in opts if str(o).strip()]
        if not options:
            return "❌ Provide at least one option."
        item_id = f"item_{uuid.uuid4().hex[:8]}"
        _forms().forms().batchUpdate(
            formId=form_id,
            body={'requests': [{
                'createItem': {
                    'item': {
                        'itemId': item_id,
                        'title': question_title,
                        'questionItem': {
                            'question': {
                                'required': required,
                                'choiceQuestion': {
                                    'type': 'RADIO',
                                    'options': options,
                                },
                            }
                        },
                    },
                    'location': {'index': 0},
                }
            }]}
        ).execute()
        return f"✅ Choice question added: '{question_title}' ({len(options)} options)."
    except Exception as e:
        return f"❌ Error adding choice question: {e}"


@mcp.tool()
def add_checkbox_question(
    form_id: str, question_title: str, options_json: str, required: bool = False
) -> str:
    """Add a checkbox question to a Form. options_json must be a JSON array."""
    form_id = form_id.strip()
    try:
        import json
        opts = json.loads(options_json)
        if not isinstance(opts, list): return "❌ options_json must be a JSON array."
        options = [{'value': str(o).strip()} for o in opts if str(o).strip()]
        item_id = f"item_{uuid.uuid4().hex[:8]}"
        _forms().forms().batchUpdate(
            formId=form_id,
            body={'requests': [{
                'createItem': {
                    'item': {
                        'itemId': item_id,
                        'title': question_title,
                        'questionItem': {
                            'question': {
                                'required': required,
                                'choiceQuestion': {
                                    'type': 'CHECKBOX',
                                    'options': options,
                                },
                            }
                        },
                    },
                    'location': {'index': 0},
                }
            }]}
        ).execute()
        return f"✅ Checkbox question added: '{question_title}'."
    except Exception as e:
        return f"❌ Error adding checkbox question: {e}"


@mcp.tool()
def update_form_info(form_id: str, title: str = "", description: str = "") -> str:
    """Update Form title or description."""
    form_id = form_id.strip()
    try:
        info = {}
        if title:
            info['title'] = title
        if description:
            info['description'] = description
        if not info:
            return "❌ Provide title and/or description."
        _forms().forms().batchUpdate(
            formId=form_id,
            body={'requests': [{'updateFormInfo': {'info': info, 'updateMask': ','.join(info.keys())}}]}
        ).execute()
        return f"✅ Form info updated."
    except Exception as e:
        return f"❌ Error updating form info: {e}"


@mcp.tool()
def delete_form_question(form_id: str, item_id: str) -> str:
    """Delete a question from a Form."""
    form_id = form_id.strip()
    try:
        _forms().forms().batchUpdate(
            formId=form_id,
            body={'requests': [{'deleteItem': {'itemId': item_id}}]}
        ).execute()
        return f"🗑️ Question item {item_id} deleted."
    except Exception as e:
        return f"❌ Error deleting question: {e}"


@mcp.tool()
def reorder_form_questions(form_id: str, item_id: str, new_index: int) -> str:
    """Reorder a question in a Form."""
    form_id = form_id.strip()
    try:
        _forms().forms().batchUpdate(
            formId=form_id,
            body={'requests': [{
                'updateItemLocation': {
                    'location': {'index': new_index},
                    'itemId': item_id,
                }
            }]}
        ).execute()
        return f"✅ Question moved to index {new_index}."
    except Exception as e:
        return f"❌ Error reordering question: {e}"


@mcp.tool()
def delete_form(form_id: str) -> str:
    """Delete a Google Form."""
    form_id = form_id.strip()
    try:
        _drive().files().delete(fileId=form_id).execute()
        return f"🗑️ Form deleted (ID: {form_id})."
    except Exception as e:
        return f"❌ Error deleting form: {e}"


@mcp.tool()
def clear_form_responses(form_id: str) -> str:
    """Clear all responses for a Form."""
    form_id = form_id.strip()
    try:
        svc = _forms()
        responses = svc.forms().responses().list(formId=form_id).execute().get('responses', [])
        if not responses:
            return "No responses to clear."
        for resp in responses:
            svc.forms().responses().delete(formId=form_id, responseId=resp['responseId']).execute()
        return f"🧹 Cleared {len(responses)} response(s)."
    except Exception as e:
        return f"❌ Error clearing responses: {e}"


@mcp.tool()
def get_form_responder_url(form_id: str) -> str:
    """Get the public responder URL for a Form."""
    form_id = form_id.strip()
    try:
        form = _forms().forms().get(formId=form_id).execute()
        url = form.get('responderUri', f"https://docs.google.com/forms/d/{form_id}/viewform")
        return f"📤 Responder URL:\n{url}"
    except Exception as e:
        return f"❌ Error getting responder URL: {e}"


@mcp.tool()
def duplicate_form(form_id: str, new_title: str) -> str:
    """Duplicate a Google Form."""
    form_id = form_id.strip()
    try:
        result = _drive().files().copy(fileId=form_id, body={'name': new_title}).execute()
        return f"✅ Form copied as '{new_title}'. ID: {result['id']}"
    except Exception as e:
        return f"❌ Error duplicating form: {e}"


if __name__ == "__main__":
    mcp.run(transport='stdio')
