def get_api_kwargs(token):
    return {
        "format": "json",
        "HTTP_AUTHORIZATION": f"JWT {token}",
        "HTTP_CLIENTSESSIONID": "test",
    }
