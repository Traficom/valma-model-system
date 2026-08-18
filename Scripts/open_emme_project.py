from argparse import ArgumentParser
from pathlib import Path

from assignment.emme_bindings.emme_project import EmmeProject

parser = ArgumentParser(epilog="Open EMME project.")
parser.add_argument(
    "--project-name",
    type=str,
    help="Name of VALMA project. Influences name of database directory")
parser.add_argument(
    "--emme-data-folder",
    type=str,
    help="Filepath to folder where EMME project is stored")
args = parser.parse_args()


EmmeProject(
    Path(args.emme_data_folder, args.project_name, args.project_name + ".emp"),
    visible=True)
