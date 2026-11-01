#!/usr/bin/env python3
"""Compatibility entry point for project certificate initialization."""
import sys
import yaml
from munch import munchify
import certificates
import helpers

with open('/webcrate/projects.yml') as stream:
    projects = munchify(yaml.safe_load(stream) or {})
project = projects[sys.argv[1]]
if project.active:
    project.name = sys.argv[1]
    print(certificates.initialize(project))
