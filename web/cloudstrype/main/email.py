from django.conf import settings
from django.core.mail import send_mail as _send_mail
from django.template import TemplateDoesNotExist
from django.template.loader import get_template, select_template


def send_mail(email_name, subject, recipients, request=None, **kwargs):
    """
    Send email.

    Wraps the default Django send_mail() function. Creates email bodies from
    templates. Can produce both text and HTML email bodies and send a multipart
    message.
    """

    # Make recipients iterable if it is not already (allow caller to pass a
    # single recipient, or a list.
    if isinstance(recipients, str):
        recipients = (recipients,)

    # A text template is required, if we can't load it, fail.
    try:
        text_template = select_template([
            'main/email/{}.txt'.format(email_name),
            'main/email/{}.text'.format(email_name),
        ])
    except TemplateDoesNotExist:
        raise ValueError('No template for email: %s' % email_name)

    # An HTML template is optional.
    try:
        html_template = get_template('main/email/{}.html'.format(email_name))
    except TemplateDoesNotExist:
        html_template = None

    # Produce our message body(s) from our templates using supplied context
    # (if any).
    message = text_template.render(context=kwargs, request=request)

    if html_template:
        html_message = html_template.render(context=kwargs, request=request)
    else:
        html_message = None

    # Build the from address.
    email_from = '%s <%s>' % settings.EMAIL_FROM

    # Send the email using the Django send_mail() function.
    _send_mail(subject, message, email_from, recipients,
               html_message=html_message)
