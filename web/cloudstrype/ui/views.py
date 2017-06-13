from django.views.generic import TemplateView
from django.shortcuts import render


class HowView(TemplateView):
    template_name = 'ui/how.html'

    def get(self, request, step=1):
        return render(request, self.template_name, {'step': step})
