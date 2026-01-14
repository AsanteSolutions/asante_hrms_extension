# Copyright (c) 2025, Asante Solutions and contributors
# For license information, please see license.txt

from time import localtime, strftime

import frappe
from frappe.model.document import Document
from frappe.utils import cint
from frappe.utils.data import get_datetime
from pyrate_limiter import Duration, Limiter, RedisBucket, RequestRate
from requests_ratelimiter import LimiterSession

rate = RequestRate(100, Duration.MINUTE)
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

			clickup_tasks = []
			for folder in clickup_folders:
				updated = False
				for project in project_list:
					if project.get('custom_clickup_id') == folder.get('id'):
						doc_name = project.get('name')
						update_project(doc_name, folder)
						updated = True
				if not updated:
					create_project(folder)

				lists = folder.get("lists")
				for list in lists:
					url = f"https://api.clickup.com/api/v2/list/{list.get('id')}/task?subtasks=true"

					response = session.get(url, headers=headers)

					response.raise_for_status()

					response_json = response.json()
					clickup_tasks = clickup_tasks + response_json.get('tasks')

			project_list = frappe.get_list('Project', fields=['name', 'custom_clickup_id'])
			task_list = frappe.get_list('Task', fields=['name','custom_clickup_id'])

			for clickup_task in clickup_tasks:
				updated = False

				for task in task_list:
					if task.get('custom_clickup_id') == clickup_task.get('id'):
						doc_name = task.get('name')
						update_task(doc_name, clickup_task)
						updated = True
				if not updated:
					create_task(clickup_task, project_list)

			task_list = frappe.get_list('Task', fields=['name','custom_clickup_id'])
			delete_tasks(task_list, clickup_tasks)
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

def create_task(task, project_list):
	doc = frappe.new_doc('Task')
	doc.subject = task.get('name')
	doc.custom_clickup_id = task.get('id')

	folder = task.get('folder')
	folder_id = folder.get('id')
	for project in project_list:
		if project.custom_clickup_id == folder_id:
			doc.project = project.name
			break
	#TODO: set status, set assignees

	priority = task.get('priority')
	if priority:
		priority_index = priority.get('orderindex')
		if priority_index == "1":
			doc.priority = "Urgent"
		elif priority_index == "2":
			doc.priority = "High"
		elif priority_index == "3":
			doc.priority = "Medium"
		elif priority_index == "4":
			doc.priority = "Low"

	# Clickup returns epoch time in milliseconds we remove the last three characters to get in
	# seconds as required by localtime
	if task.get('start_date'):
		doc.exp_start_date = get_datetime(strftime('%Y-%m-%d %H:%M:%S',
											 localtime(cint(task.get('start_date')[:-3]))))
	if task.get('due_date'):
		doc.exp_end_date = get_datetime(strftime('%Y-%m-%d %H:%M:%S',
										   localtime(cint(task.get('due_date')[:-3]))))

	doc.insert()

def update_task(doc_name, task):
	doc = frappe.get_doc('Task', doc_name)
	task_subject = task.get('name')
	if doc.subject != task_subject:
		doc.subject = task_subject
	#TODO: set status, set assignees

	priority = task.get('priority')
	if priority:
		priority_index = priority.get('orderindex')
		if priority_index == "1":
			doc.priority = "Urgent"
		elif priority_index == "2":
			doc.priority = "High"
		elif priority_index == "3":
			doc.priority = "Medium"
		elif priority_index == "4":
			doc.priority = "Low"

	# Clickup returns epoch time in milliseconds we remove the last three characters to get in
	# seconds as required by localtime
	if task.get('start_date'):
		doc.exp_start_date = get_datetime(strftime('%Y-%m-%d %H:%M:%S',
											 localtime(cint(task.get('start_date')[:-3]))))
	if task.get('due_date'):
		doc.exp_end_date = get_datetime(strftime('%Y-%m-%d %H:%M:%S',
										   localtime(cint(task.get('due_date')[:-3]))))

	doc.save()

def delete_tasks(task_list, clickup_tasks):
	for task in task_list:
		match = False
		for clickup_task in clickup_tasks:
			if task.get('custom_clickup_id') == clickup_task.get('id'):
				match = True
				break
		if not match:
			frappe.delete_doc('Task', f"{task.get('name')}")
