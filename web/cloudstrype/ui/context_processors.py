from django.conf import settings


def version(request):
    """
    Make version globally available to templates.

    The version is used on the bottom of the main template and all derived
    templates to generate a link to the specific commit that is currently
    deployed.
    """

    return {
        'CLOUDSTRYPE_VERSION': settings.CLOUDSTRYPE_VERSION,
    }
