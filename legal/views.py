from django.views.generic import TemplateView


class PrivacyPolicyView(TemplateView):
    template_name = 'legal/privacy.html'


class TermsOfServiceView(TemplateView):
    template_name = 'legal/terms.html'
