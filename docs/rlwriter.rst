RlWriter Documentation
=====================

Overview
--------

The RlWriter class is responsible for generating PDF documents from MediaWiki content using the ReportLab library. This document explains how the RlWriter works, focusing on the sequence of function calls, debugging options, and how title and front matter are rendered.

Initialization Process
---------------------

The RlWriter class is initialized with the following parameters:

.. code-block:: python

    def __init__(
        self,
        env=None,
        strict=False,
        debug=False,
        mathcache=None,
        lang=None,
        test_mode=False,
    ):

- ``env``: The environment object containing the wiki, metabook, and images
- ``strict``: Flag to raise exceptions on errors
- ``debug``: Flag to enable verbose debugging
- ``mathcache``: Directory for caching math images
- ``lang``: Language for translations
- ``test_mode``: Flag for test mode

During initialization, the RlWriter:

1. Sets up language translations
2. Configures font handling with ``fontconfig.RLFontSwitcher``
3. Handles right-to-left (RTL) text if needed
4. Sets up the environment, book, and image database
5. Initializes the license checker
6. Configures tree cleaning and node transformation
7. Sets up various counters and state variables

Sequence of Function Calls
-------------------------

The main workflow of the RlWriter follows this sequence:

1. **Entry Point**: The ``writer()`` function creates an RlWriter instance and calls ``writeBook()``

2. **Book Writing Process**:
   - ``writeBook()``: Main method that orchestrates the PDF generation
     - Initializes the ReportLab document with ``initReportlabDoc()``
     - Adds title page if configured with ``writeTitlePage()``
     - Processes each item in the metabook (chapters and articles)
     - Renders the book with ``renderBook()``

3. **Article Processing**:
   - ``buildArticle()``: Parses and prepares the article
     - Gets the parsed article from the wiki
     - Builds the advanced tree with ``advtree.build_advanced_tree()``
     - Cleans the tree with ``tree_cleaner.clean_all()``
     - Transforms CSS with ``cnt.transform_css()``

   - ``writeArticle()``: Renders an article to PDF elements
     - Renders the article title
     - Processes the article content with ``renderMixed()``
     - Handles images with ``floatImages()`` and ``tabularizeImages()``
     - Adds references

4. **Content Rendering**:
   - ``renderMixed()``: Renders mixed content nodes
   - Various ``write*`` methods for specific node types:
     - ``writeArticle()``: Renders an article
     - ``writeChapter()``: Renders a chapter
     - ``writeParagraph()``: Renders a paragraph
     - ``writeText()``: Renders text
     - ``writeImageLink()``: Renders image links
     - ``writeTable()``: Renders tables
     - etc.

5. **Final Rendering**:
   - ``renderBook()``: Finalizes and builds the PDF
     - Adds metadata and references
     - Adds license information
     - Builds the document with ``doc.build()``
     - Renders the table of contents if configured

Debugging the Document Tree
--------------------------

To debug the document tree and look for render errors:

1. **Enable Debug Mode**: Pass ``debug=True`` when creating the RlWriter instance:
   
   .. code-block:: python
   
      rl_writer = RlWriter(env, debug=True)

2. **Debug Output**: When debug mode is enabled:
   - The parsed tree is printed to stdout with ``parser.show(sys.stdout, art)``
   - Tree cleaner reports are logged with ``log.info("\n".join([repr(r) for r in self.tree_cleaner.get_reports()]))``
   - Additional debug information is logged throughout the rendering process

3. **Fail-Safe Rendering**: If rendering fails, the RlWriter attempts a fail-safe rendering:
   
   .. code-block:: python
   
      if self.fail_safe_rendering and not self.articleRenderingOK(copy.deepcopy(art), output):
          art.renderFailed = True

4. **Error Handling**: Errors during rendering are caught and logged:
   
   .. code-block:: python
   
      except Exception as err:
          traceback.print_exc()
          log.error("RENDERING FAILED: %r" % err)

Title and Front Matter Rendering
-------------------------------

The title page and front matter are rendered as follows:

1. **Title Page**: Controlled by ``pdfstyles.SHOW_TITLE_PAGE``
   - If enabled and there is more than one article, ``writeTitlePage()`` is called to generate the title page
   - The title page is skipped when there is only a single article, regardless of the ``SHOW_TITLE_PAGE`` setting
   - The title page includes:
     - Book title
     - Subtitle (if available)
     - Editor information
     - Cover image (if provided)

2. **Title Page Template**: The ``TitlePage`` class in ``pagetemplates.py`` defines the layout:
   
   .. code-block:: python
   
      title_page = TitlePage(
          self.book.title or "",
          self.book.subtitle or "",
          self.getAuthor(),
          coverimage,
      )

3. **Article Titles**: Each article's title is rendered with:
   
   .. code-block:: python
   
      heading_para = Paragraph(
          f"<b>{title}</b>{heading_anchor}", heading_style("article")
      )

4. **Chapter Headings**: Chapter titles are rendered with:
   
   .. code-block:: python
   
      elements.append(Paragraph(title, heading_style("chapter")))

5. **Table of Contents**: If enabled (``pdfstyles.RENDER_TOC``), a table of contents is generated:
   
   .. code-block:: python
   
      if pdfstyles.RENDER_TOC and self.numarticles > 1:
          self.toc_renderer.build(
              output,
              self.toc_entries,
              has_title_page=bool(self.book.title),
              rtl=self.rtl,
          )

Customization Options
--------------------

The RlWriter supports several customization options:

1. **Cover Image**: Specify a cover image for the title page
   
   .. code-block:: none
   
      --writer-options coverimage=FILENAME

2. **Strict Mode**: Raise exceptions on errors
   
   .. code-block:: none
   
      --writer-options strict

3. **Debug Mode**: Enable verbose debugging
   
   .. code-block:: none
   
      --writer-options debug

4. **Math Cache**: Specify a directory for caching math images
   
   .. code-block:: none
   
      --writer-options mathcache=DIRNAME

5. **Language**: Specify the language for translations
   
   .. code-block:: none
   
      --writer-options lang=LANGUAGE

6. **Profiling**: Profile the rendering process (for debugging only)
   
   .. code-block:: none
   
      --writer-options profile=PROFILEFN

These options can be configured through the ``writer()`` function or via command-line arguments to ``mw-render``.
