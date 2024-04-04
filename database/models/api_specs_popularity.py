from model import Model

class ApiSpecsPopularity( Model ):
    table = 'api_specs_popularity'
    id = None
    api_spec_id = None
    owner  = None
    repo_name  = None
    forks = None
    stars = None
    watching = None
    created_at = None
    updated_at = None
    unique_fields = []

    def __init__(self):
        super().__init__()