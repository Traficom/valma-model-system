from argparse import ArgumentParser

import inro.emme.desktop.app as _app

parser = ArgumentParser(epilog="Create empty EMME project.")
parser.add_argument(
    "--project-name",
    type=str,
    help="Name of VALMA project. Influences name of database directory")
parser.add_argument(
    "--emme-path",
    type=str,
    help="Filepath to folder where EMME project will be created")
args = parser.parse_args()

_app.create_project(args.emme_path, args.project_name)
