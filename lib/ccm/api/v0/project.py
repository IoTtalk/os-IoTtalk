"""
Project Moduel.

    reopen_project

    create
    list_
    get
    update
    delete
"""
import hashlib
import logging

import ControlChannel
import db

from flask import g, request

from ccm.api.utils import (blueprint, invalid_input,
                           json_data, json_error, record_parser)

api = blueprint(__name__, __file__)
log = logging.getLogger("ccm.api.v0.api")


def reopen_project(p_id):
    session = g.session
    project = (session.query(db.Project)
                      .filter(db.Project.p_id == p_id)
                      .first())

    project.restart = 1
    session.commit()


@api.route('/', methods=['PUT'], strict_slashes=False)
def create():
    """
    Create a new Project.

    Request:

        {
            'p_name': 'project name',
        }

    Response HTTP 201:

        {
            'state': 'ok',
            'p_id': 42,
        }

    Response if project name duplicated:

        {
            'state': 'error',
            'reason': 'project name already exists',
        }
    """
    err = invalid_input(request.json, {'p_name': str})
    if err:
        return json_error(err)

    session = g.session

    p_name = request.json.get('p_name').strip()
    p_pwd = request.json.get('p_pwd', '')

    # check project name
    if not p_name:
        return json_error('Project name must be visible.')
    # check exist
    p_record = (session.query(db.Project)
                       .filter(db.Project.p_name == p_name)
                       .first())
    if p_record:
        return json_error('Project name is already exsitd')

    # encrypt password
    m = hashlib.md5()
    m.update(p_pwd.encode('utf-8'))
    p_pwd = m.hexdigest()

    new_project = db.Project(
        p_name=p_name,
        pwd=p_pwd,
        status='on',
        restart=0,
        u_id=1,
        exception='',
        sim='off'
    )
    session.add(new_project)
    session.commit()

    return json_data(p_id=new_project.p_id)


@api.route('/', methods=['GET'], strict_slashes=False)
def list_():
    """
    Get all Project.

    Response:

        {
            'state': 'ok',
            'data': [
                {
                    'exception': '',
                    'p_id': 1,
                    'p_name': 'test',
                    'restart': false,
                    'sim': 'off',
                    'status': 'on',
                    'u_id': 1
                },
            ],
        }
    """
    session = g.session
    project_list = session.query(db.Project).order_by(db.Project.p_name).all()
    data = []
    for project in project_list:
        p = record_parser(project)
        if 'pwd' in p:
            p.pop('pwd')
        data.append(p)

    return json_data(data=data)


@api.route('/<int:p_id>', methods=['GET'], strict_slashes=False)
def get(p_id):
    """
    Get detailed information about Project by p_id.

    Response:

        {
            'state': 'ok',
            'data': {
                // project info
            },
        }

    Response if not project not found, HTTP 404 is returned:

        {
            'state': 'error',
            'reason': 'project not found',
        }
    """
    session = g.session
    project_record = (session.query(db.Project)
                             .filter(db.Project.p_id == p_id)
                             .first())
    if not project_record:
        return json_error('Project not found.')

    project = record_parser(project_record)
    project.pop('pwd')
    return json_data(data=project)


@api.route('/<int:p_id>', methods=['POST'], strict_slashes=False)
def update(p_id):
    """
    Update a project status.

    Request:

        {
            'status': 'on' | 'off',
        }

    Response:

        {
            'state': 'ok',
            'p_id': 42,
            'status': 'on',
        }
    """
    session = g.session

    status = request.json.get('status')

    # check exist
    project_record = (session.query(db.Project)
                             .filter(db.Project.p_id == p_id)
                             .first())

    if not project_record:
        return json_error('Project not found.')

    # check status is valid and set ControlChannel
    if status == 'on':
        ControlChannel.RESUME(db, p_id)
    elif status == 'off':
        ControlChannel.SUSPEND(db, p_id)
    else:
        return json_error('invalid status')

    project_record.status = status
    session.commit()

    return json_data(p_id=p_id, status=status)


@api.route('/<int:p_id>', methods=['DELETE'], strict_slashes=False)
def delete(p_id):
    """
    Delete an exist Project.

    Response:

        {
            'state': 'ok',
            'p_id': 42,
        }

    Response if project not found:

        {
            'state': 'error',
            'reason': 'project 42 not found',
        }
    """
    session = g.session

    # query NetworkApplication
    na_records = (session.query(db.NetworkApplication)
                         .filter(db.NetworkApplication.p_id == p_id)
                         .all())

    # delete MultipleJoin_Module, DFModule, NetworkApplication
    for na in na_records:
        # delete MultipleJoin_Module
        (session.query(db.MultipleJoin_Module)
                .filter(db.MultipleJoin_Module.na_id == na.na_id)
                .delete())
        session.commit()

        # delete DFModule
        (session.query(db.DF_Module)
                .filter(db.DF_Module.na_id == na.na_id)
                .delete())
        session.commit()

        # delete NetworkApplication
        session.delete(na)
        session.commit()

    # query DeviceObject
    do_records = (session.query(db.DeviceObject.do_id)
                         .filter(db.DeviceObject.p_id == p_id)
                         .all())

    # delete DFObject, DeviceObject
    for do in do_records:
        # delete DFObject
        (session.query(db.DFObject)
                .filter(db.DFObject.do_id == do.do_id)
                .delete())
        session.commit()

        # delete DeviceObject
        (session.query(db.DeviceObject)
                .filter(db.DeviceObject.do_id == do.do_id)
                .delete())
        session.commit()

    # delete Project
    (session.query(db.Project)
            .filter(db.Project.p_id == p_id)
            .delete())
    session.commit()

    return json_data(p_id=p_id)
