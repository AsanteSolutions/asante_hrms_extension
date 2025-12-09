# Copyright (c) 2025, Asante Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from pyrate_limiter import Duration, Limiter, RedisBucket, RequestRate
from requests_ratelimiter import LimiterSession

rate = RequestRate(100, Duration.MINUTE * 5)
limiter = Limiter(rate)
session = LimiterSession(limiter=limiter, bucket_class=RedisBucket)

class ClickupIntegration(Document):
	pass

def update_projects_from_clickup() -> None:
	doc = frappe.get_doc('Clickup Integration')
	headers = {}

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

		url = f"https://api.clickup.com/api/v2/team/{doc.workspace_id}/space"

		try:
			response = session.get(url, headers=headers)

			response.raise_for_status()

			response_json = response.json()
			spaces = response_json.get('spaces')

			clickup_folders = []
			for space in spaces:
				url = f"https://api.clickup.com/api/v2/space/{space.get('id')}/folder"

				response = session.get(url, headers=headers)

				response.raise_for_status()

				response_json = response.json()
				clickup_folders = clickup_folders + response_json.get('folders')


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
			doc.log_error(title="Bad response from ClickUp request", message=str(e))



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




