import warnings

from pyramid.exceptions import NotFound
from pyramid.view import render_view_to_response

from kotti.resources import Document

def view_content_default(context, request):
    """This view is always registered as the default view for any Content.

    Its job is to delegate to a view of which the name may be defined
    per instance.  If a instance level view is not defined for
    'context' (in 'context.defaultview'), we will fall back to a view
    with the name 'view'.
    """
    view_name = context.default_view or 'view'
    response = render_view_to_response(context, request, name=view_name)
    if response is None: # pragma: no coverage
        warnings.warn("Failed to look up default view called %r for %r" %
                      (view_name, context))
        raise NotFound()
    return response

def view_node(context, request):
    return {}

def includeme(config):
    config.add_view(
        view_node,
        context=Document,
        name='view',
        permission='view',
        renderer='../templates/view/document.pt',
        )
