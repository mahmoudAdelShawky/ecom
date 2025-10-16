from django.shortcuts import render

class ErrorHandlerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        context = {'error_message': str(exception)}
        return render(request, 'error.html', context, status=500)