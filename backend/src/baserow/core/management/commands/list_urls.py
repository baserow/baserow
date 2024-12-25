from django.core.management.base import BaseCommand
from django.urls import URLPattern, URLResolver, get_resolver


class Command(BaseCommand):
    help = "List all registered full URLs with their namespaces"

    def handle(self, *args, **kwargs):
        resolver = get_resolver()
        self.list_urls(resolver.url_patterns)

    def list_urls(self, urlpatterns, prefix="", namespace=None):
        for pattern in urlpatterns:
            if isinstance(pattern, URLPattern):
                # Construct the full URL path
                full_url = f"{prefix}{pattern.pattern}"
                full_namespace = (
                    f"{namespace}:{pattern.name}"
                    if namespace and pattern.name
                    else pattern.name or "None"
                )
                self.stdout.write(f"URL: {full_url}, Namespace: {full_namespace}")
            elif isinstance(pattern, URLResolver):
                # Construct the full namespace and recurse
                new_prefix = f"{prefix}{pattern.pattern}"
                new_namespace = (
                    f"{namespace}:{pattern.namespace}"
                    if namespace and pattern.namespace
                    else pattern.namespace or namespace
                )
                self.list_urls(
                    pattern.url_patterns, prefix=new_prefix, namespace=new_namespace
                )
