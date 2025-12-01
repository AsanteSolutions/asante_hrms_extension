# Copyright (c) 2025, Asante Solutions and contributors
# For license information, please see license.txt

import frappe
import requests
from frappe.model.document import Document


class ClickupIntegration(Document):
	pass

def update_projects_from_clickup():
	doc = frappe.get_doc('Clickup Integration')

	if doc.api_key or doc.access_token:
		if doc.api_key:
			headers = {
				"accept": "application/json",
				"Authorization": f"{doc.get_password('api_key')}"
			}
		elif doc.access_token:
			headers = {
				"accept": "application/json",
				"Authorization": f"Bearer {doc.get_password('access_token')}"
			}

		url = f"https://api.clickup.com/api/v2/space/{doc.space_id}/folder"

		try:
			response = requests.get(url, headers=headers)

			response.raise_for_status()

			respone_json = response.json()
			clickup_folders = respone_json.get('folders')
			project_list = frappe.get_list('Project', fields=['name', 'custom_clickup_id'])

			for folder in clickup_folders:
				updated = False
				for project in project_list:
					if project.get('custom_clickup_id') == folder.get('id'):
						doc_name = project.get('name')
						update_project(doc_name, folder)
						updated = True
				if not updated:
					create_project(folder)

			delete_projects(project_list, clickup_folders)

		except Exception as e:
			doc.log_error(title="Bad response from Clickup request", message=str(e))


def create_project(folder):
	doc = frappe.new_doc('Project')
	doc.project_name = folder.get('name')
	doc.custom_clickup_id = folder.get('id')
	doc.insert()

def update_project(doc_name, folder):
	doc = frappe.get_doc('Project', doc_name)
	project_name = folder.get('name')
	if doc.project_name != project_name:
		doc.project_name = project_name
	doc.save()

def delete_projects(project_list, clickup_folders):
	for project in project_list:
		match = False
		for folder in clickup_folders:
			if project.get('custom_clickup_id') == folder.get('id'):
				match = True
				break
		if not match:
			frappe.delete_doc('Project', f"{project.get('name')}")




