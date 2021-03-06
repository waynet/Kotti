import pkg_resources

from sqlalchemy import engine_from_config
from sqlalchemy import MetaData
from sqlalchemy.sql.expression import desc
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.config import Configurator
from pyramid.events import BeforeRender
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from pyramid.threadlocal import get_current_registry
from pyramid.util import DottedNameResolver

import kotti.patches; kotti.patches
from kotti.util import request_cache

metadata = MetaData()
DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))

def authtkt_factory(**settings):
    from kotti.security import list_groups_callback
    return AuthTktAuthenticationPolicy(
        secret=settings['kotti.secret2'], callback=list_groups_callback)

def acl_factory(**settings):
    return ACLAuthorizationPolicy()

def cookie_session_factory(**settings):
    secret = settings['kotti.secret2']
    return UnencryptedCookieSessionFactoryConfig(secret)

def none_factory(**kwargs): # pragma: no cover
    return None

# All of these can be set by passing them in the Paste Deploy settings:
conf_defaults = {
    'kotti.templates.master_view': 'kotti:templates/view/master.pt',
    'kotti.templates.master_edit': 'kotti:templates/edit/master.pt',
    'kotti.templates.master_cp': 'kotti:templates/site-setup/master.pt',
    'kotti.templates.snippets': 'kotti:templates/snippets.pt',
    'kotti.templates.base_css': 'kotti:static/base.css',
    'kotti.templates.view_css': 'kotti:static/view.css',
    'kotti.templates.edit_css': 'kotti:static/edit.css',
    'kotti.templates.api': 'kotti.views.util.TemplateAPI',
    'kotti.configurators': '',
    'kotti.base_includes': 'kotti.events kotti.views.view kotti.views.edit kotti.views.login kotti.views.users kotti.views.site_setup kotti.views.slots',
    'kotti.includes': '',
    'kotti.populators': 'kotti.resources.populate',
    'kotti.available_types': 'kotti.resources.Document',
    'kotti.authn_policy_factory': 'kotti.authtkt_factory',
    'kotti.authz_policy_factory': 'kotti.acl_factory',
    'kotti.session_factory': 'kotti.cookie_session_factory',
    'kotti.principals_factory': 'kotti.security.principals_factory',
    'kotti.date_format': 'medium',
    'kotti.datetime_format': 'medium',
    'kotti.time_format': 'medium',
    }

conf_dotted = set([
    'kotti.templates.api',
    'kotti.configurators',
    'kotti.base_includes',
    'kotti.includes',
    'kotti.populators',
    'kotti.available_types',
    'kotti.authn_policy_factory',
    'kotti.authz_policy_factory',
    'kotti.session_factory',
    'kotti.principals_factory',
    ])

def get_version():
    return pkg_resources.require("Kotti")[0].version

@request_cache(lambda: None)
def get_settings():
    from kotti.resources import Settings
    session = DBSession()
    db_settings = session.query(Settings).order_by(desc(Settings.id)).first()
    if db_settings is not None:
        reg_settings = dict(get_current_registry().settings)
        reg_settings.update(db_settings.data)
        return reg_settings
    else:
        return get_current_registry().settings

def _resolve_dotted(d, keys=conf_dotted):
    for key in keys:
        value = d[key]
        if not isinstance(value, basestring):
            continue
        new_value = []
        for dottedname in value.split():
            new_value.append(DottedNameResolver(None).resolve(dottedname))
        d[key] = new_value

def main(global_config, **settings):
    """ This function returns a WSGI application.
    """
    for key, value in conf_defaults.items():
        settings.setdefault(key, value)

    _resolve_dotted(settings, keys=('kotti.configurators',))

    # Allow extending packages to change 'settings' w/ Python:
    for func in settings['kotti.configurators']:
        func(settings)

    _resolve_dotted(settings)

    secret1 = settings['kotti.secret']
    settings.setdefault('kotti.secret2', secret1)

    authentication_policy = settings[
        'kotti.authn_policy_factory'][0](**settings)
    authorization_policy = settings[
        'kotti.authz_policy_factory'][0](**settings)
    session_factory = settings['kotti.session_factory'][0](**settings)

    config = Configurator(
        settings=settings,
        authentication_policy=authentication_policy,
        authorization_policy=authorization_policy,
        session_factory=session_factory,
        )

    config.begin()
    config.commit()

    # Include modules listed in 'kotti.base_includes' and 'kotti.includes':
    for module in (
        settings['kotti.base_includes'] + settings['kotti.includes']):
        config.include(module)

    from kotti.resources import appmaker
    engine = engine_from_config(settings, 'sqlalchemy.')
    config._set_root_factory(appmaker(engine))

    import kotti.views.util
    config.add_subscriber(
        kotti.views.util.add_renderer_globals, BeforeRender)
    
    _configure_base_views(config)

    return config.make_wsgi_app()

def _configure_base_views(config):
    from kotti.resources import IContent

    config.add_static_view('static-deform', 'deform:static')
    config.add_static_view('static-kotti', 'kotti:static')
    config.add_view('kotti.views.view.view_content_default', context=IContent)
    config.add_view(
        'kotti.views.edit.add_node',
        name='add',
        permission='add',
        renderer='templates/edit/add.pt',
        )
    config.add_view(
        'kotti.views.edit.move_node',
        name='move',
        permission='edit',
        renderer='templates/edit/move.pt',
        )
