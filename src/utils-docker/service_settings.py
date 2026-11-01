"""Shared service enablement rules."""
import os


def enabled(name):
    flags = {'grafana': 'STATS', 'doctohtml': 'DOCTOHTML', 'htmltopdf': 'HTMLTOPDF',
             'docxtopdf': 'DOCXTOPDF', 'pdffooter': 'PDFFOOTER'}
    return name not in flags or os.environ.get(f'WEBCRATE_SERVICE_{flags[name]}', 'false') == 'true'
