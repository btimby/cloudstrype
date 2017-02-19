from django import forms


class OAuthForm(forms.Form):
    # TODO: need to perform OAuth flow. Hopefully we can use parts of allauth
    # to pull this off. We will need to specify additional scopes.
    pass


class DesktopArrayForm(forms.Form):
    # TODO: define what is necessary here, will be determined when desktop
    # array system is built.
    pass


class S3Form(forms.Form):
    bucket = forms.CharField(label='Bucket', max_length=100)
    access_key = forms.CharField(label='Access key', max_length=100)
    secret_key = forms.CharField(label='Secret key', max_length=100)


class URLForm(forms.Form):
    host = forms.CharField(label='Hostname', max_length=100)
    username = forms.CharField(label='Username', max_length=100)
    password = forms.CharField(label='Password', max_length=100)
