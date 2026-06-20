from flask import jsonify


def success(data=None, message="ok", status_code=200):
    body = {"message": message}
    if data is not None:
        body["data"] = data
    return jsonify(body), status_code


def created(data=None, message="created"):
    return success(data, message, 201)
