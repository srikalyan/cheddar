"""
URL mappings for package index functionality.
"""
from collections import OrderedDict
from functools import wraps
from pkg_resources import parse_version

from flask import abort, make_response, render_template, request

from cheddar.auth import check_authentication
from cheddar.local import guess_name_and_version


def create_routes(app):

    def authenticated(func):
        """
        Basic Auth decorator.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not check_authentication(app.redis):
                response = make_response("", 401)
                response.headers["WWW-Authenticate"] = 'Basic realm="cheddar"'
                return response
            return func(*args, **kwargs)
        return wrapper

    @app.route("/")
    def index():
        """
        Index page.
        """
        return render_template("index.html")

    @app.route("/simple/")
    @app.route("/simple")
    def simple():
        """
        Simple package index.

        Lists known packages.
        """
        return render_template("simple.html",
                               packages=sorted(app.index.get_local_packages()))

    @app.route("/simple/<name>/")
    @app.route("/simple/<name>")
    def get_package(name):
        """
        Simple package index for a single package.

        Lists known releases and their locations.
        """
        releases = app.index.get_available_releases(name)

        def sort_key(name):
            _, version = guess_name_and_version(name)
            return parse_version(version)

        sorted_releases = OrderedDict()
        for name in sorted(releases.keys(), key=sort_key):
            sorted_releases[name] = releases[name]

        return render_template("package.html",
                               releases=sorted_releases)

    @app.route("/local/<path:path>/")
    @app.route("/local/<path:path>")
    def get_local_distribution(path):
        """
        Local distribution download access.
        """
        content_data, content_type = app.index.get_release(path, True)
        response = make_response(content_data)
        response.headers['Content-Type'] = content_type
        return response

    @app.route("/remote/<path:path>/")
    @app.route("/remote/<path:path>")
    def get_remote_distribution(path):
        """
        Remote distribution download access.

        Proxies and caches content.
        """
        content_data, content_type = app.index.get_release(path, False)
        response = make_response(content_data)
        response.headers['Content-Type'] = content_type
        return response

    @app.route("/pypi/", methods=["POST"])
    @app.route("/pypi", methods=["POST"])
    def pypi():
        """
        PyPI upload endpoint, handles setuptools register and upload commands.
        """
        if "content" in request.files:
            return upload()
        elif "name" in request.form and "version" in request.form:
            return register()
        else:
            abort(400)

    @authenticated
    def upload():
        """
        Upload distribution data. Requires auth.
        """
        app.index.upload(request.files["content"])
        return ""

    def register():
        """
        Register a distribution.

        For no reason that I understand, setuptools does not send Basic Auth
        credentials for register, so this is *not* authenticated.
        """
        data = {key: values[0] for key, values in request.form.iterlists()}
        app.index.register(data["name"], data["version"], data)
        return ""
