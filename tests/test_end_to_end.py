import os
import subprocess
import tempfile
import unittest

import click
import pytest
from pypdf import PdfReader


@click.command()
@click.option(
    "--collection-dir",
    type=click.Path(exists=True, file_okay=False),
    default="./sample_collections",
    help="Path to the directory containing collection files",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, writable=True),
    default="./sample_collections_output",
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


@pytest.mark.integration
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
            f"workdir={self.workdir}",
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
        assert self.collection_dir is not None
        for collection_name in COLLECTIONS:
            # Check if either collection_name.json or collection_name.zip exists
            json_file = os.path.join(self.collection_dir, f"{collection_name}.json")
            zip_file = os.path.join(self.collection_dir, f"{collection_name}.zip")
            if not (os.path.exists(json_file) or os.path.exists(zip_file)):
                print(f"Skipping {collection_name}: Neither {json_file} nor {zip_file} exists")
                continue

            with self.subTest(collection=collection_name):
                self.run_buildzip(collection_name)
                self.run_render(collection_name)
                self.validate_pdf(collection_name)


if __name__ == "__main__":
    main()
