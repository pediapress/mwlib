import os
import subprocess
import unittest

import click
from PyPDF2 import PdfReader


@click.command()
@click.option(
    "--collection-dir",
    type=click.Path(exists=True, file_okay=False),
    default="/home/fingon/Dev/pediapress/mwlib.pdf/assets/test_files",
    help="Path to the directory containing collection files",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, writable=True),
    default="/home/fingon/Dev/pediapress/hiq",
    help="Path to the directory where outputs will be saved",
)
def main(collection_dir, output_dir):
    """Main entry point to configure and run the tests."""
    # Ensure workdir exists
    workdir = os.path.join(output_dir, "workdir")
    os.makedirs(workdir, exist_ok=True)

    # Set up test environment variables
    TestBuildAndRender.collection_dir = collection_dir
    TestBuildAndRender.output_dir = output_dir
    TestBuildAndRender.workdir = workdir

    # Run unittest
    unittest.main(argv=[""], exit=False)


COLLECTIONS = [
    "bengali",
    "the_nether_world",
    "premier",
    "10random",
    "wpeu_person",
    "i18n_math",
    "iotation",
    "schroedinger",
    "mainz",
    "10chapter",
    "wikimedia_maps",
    "local_cities",
    "element",
    "wpeu_100_articles",
    "wpeu_begonako_errepublika",
    "san_francisco",
    "hogwarts_express",
    "amphibious_aircrafts",
    "chinese_script",
    "maxwell",
    "wiesbaden",
]


class TestBuildAndRender(unittest.TestCase):
    collection_dir = None
    output_dir = None
    workdir = None

    def run_buildzip(self, collection_name):
        """Run the BuildZip command."""
        print(f"Building ZIP for {collection_name}")
        input_file = os.path.join(self.collection_dir, f"{collection_name}.json")
        self.output_zip = os.path.join(self.output_dir, f"{collection_name}.zip")

        command = [
            "python",
            "src/mwlib/apps/buildzip.py",
            "-m",
            input_file,
            "--output",
            self.output_zip,
        ]
        env = os.environ.copy()
        env["GEVENT_SUPPORT"] = "True"
        env["MWLIB_PYPROJECT_TOML"] = "pyproject.toml"

        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"BuildZip failed for {collection_name}: {result.stderr}")

    def run_render(self, collection_name):
        """Run the Render command."""
        print(f"Rendering PDF for {collection_name}")
        self.output_pdf = os.path.join(self.output_dir, f"{collection_name}.pdf")

        command = [
            "python",
            "src/mwlib/apps/render.py",
            "-w",
            "xl",
            "-o",
            self.output_pdf,
            "-c",
            self.output_zip,
            "-Len",
            "--writer-options",
            f"wokrdir={self.workdir}",
        ]
        env = os.environ.copy()
        env["GEVENT_SUPPORT"] = "True"

        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"Render failed for {collection_name}: {result.stderr}")

    def validate_pdf(self, collection_name):
        """Validate the generated PDF."""

        print(f"Validating PDF for {collection_name}")
        self.assertTrue(
            os.path.exists(self.output_pdf), f"Output PDF file does not exist for {collection_name}."
        )
        try:
            reader = PdfReader(self.output_pdf)
            num_pages = len(reader.pages)
            self.assertGreater(num_pages, 0, f"Generated PDF has zero pages for {collection_name}.")
            print(f"Generated PDF has {num_pages} pages for {collection_name}")
        except Exception as e:
            self.fail(f"Generated PDF is invalid for {collection_name}: {e}")

    def test_build_and_render(self):
        """Run BuildZip and Render for each collection name and validate the PDF."""
        for collection_name in COLLECTIONS:
            with self.subTest(collection=collection_name):
                self.run_buildzip(collection_name)
                self.run_render(collection_name)
                self.validate_pdf(collection_name)


if __name__ == "__main__":
    main()
