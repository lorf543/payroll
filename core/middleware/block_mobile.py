from django.http import HttpResponseForbidden

class BlockMobileMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        
        if request.user.is_authenticated and request.user.is_staff:
            return self.get_response(request)

        user_agent = request.user_agent

        # Bloquear móviles y tablets para usuarios normales
        if user_agent.is_mobile or user_agent.is_tablet:
            return HttpResponseForbidden(
                "<h1>Not allowed to login from phones or tablets.</h1>"
            )

        return self.get_response(request)
