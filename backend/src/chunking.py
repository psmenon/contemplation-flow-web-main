# Copyright © 2025- Yash Bonde
# Copyright © 2024-2025 Frello Technology Private Limited

from typing import List
from dataclasses import dataclass

import fitz
import docx
import string
import tiktoken
from docx import Document
from tqdm.asyncio import trange


@dataclass
class Chunk:
    id: int
    content: str
    loc: str


# processing based on mimetypes


async def extract_pdf_text(stream, min_size: int = 10) -> List[Chunk]:
    """Process the document and return the text of its selected pages."""
    doc = fitz.open(stream=stream, filetype="pdf")
    if isinstance(doc, str):
        doc = fitz.open(doc)
    SPACES = set(string.whitespace)  # used to check relevance of text pieces
    pages = range(doc.page_count)

    class IdentifyHeaders:
        """Compute data for identifying header text."""

        def __init__(self, doc, pages: list = None, body_limit: float = None):
            """Read all text and make a dictionary of fontsizes.

            Args:
                pages: optional list of pages to consider
                body_limit: consider text with larger font size as some header
            """
            if pages is None:  # use all pages if omitted
                pages = range(doc.page_count)
            fontsizes = {}
            for pno in pages:
                page = doc[pno]
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
                for span in [  # look at all non-empty horizontal spans
                    s
                    for b in blocks
                    for l in b["lines"]
                    for s in l["spans"]
                    if not SPACES.issuperset(s["text"])
                ]:
                    fontsz = round(span["size"])
                    count = fontsizes.get(fontsz, 0) + len(span["text"].strip())
                    fontsizes[fontsz] = count

            # maps a fontsize to a string of multiple # header tag characters
            self.header_id = {}

            if not fontsizes:
                self.header_id = {}  # Return empty header_id if no text found
                return

            if body_limit is None:  # body text fontsize if not provided
                body_limit = sorted(
                    [(k, v) for k, v in fontsizes.items()],
                    key=lambda i: i[1],
                    reverse=True,
                )[0][0]

            sizes = sorted(
                [f for f in fontsizes.keys() if f > body_limit], reverse=True
            )

            # make the header tag dictionary
            for i, size in enumerate(sizes):
                self.header_id[size] = "#" * (i + 1) + " "

        def get_header_id(self, span):
            """Return appropriate markdown header prefix.

            Given a text span from a "dict"/"radict" extraction, determine the
            markdown header prefix string of 0 to many concatenated '#' characters.
            """
            fontsize = round(span["size"])  # compute fontsize
            hdr_id = self.header_id.get(fontsize, "")
            return hdr_id

    def resolve_links(links, span):
        """Accept a span bbox and return a markdown link string."""
        bbox = fitz.Rect(span["bbox"])  # span bbox
        # a link should overlap at least 70% of the span
        bbox_area = 0.7 * abs(bbox)
        for link in links:
            hot = link["from"]  # the hot area of the link
            if not abs(hot & bbox) >= bbox_area:
                continue  # does not touch the bbox
            text = f'[{span["text"].strip()}]({link["uri"]})'
            return text

    def write_text(page, clip, hdr_prefix):
        """Output the text found inside the given clip.

        This is an alternative for plain text in that it outputs
        text enriched with markdown styling.
        The logic is capable of recognizing headers, body text, code blocks,
        inline code, bold, italic and bold-italic styling.
        There is also some effort for list supported (ordered / unordered) in
        that typical characters are replaced by respective markdown characters.
        """
        out_string = ""
        code = False  # mode indicator: outputting code

        # extract URL type links on page
        links = [l for l in page.get_links() if l["kind"] == 2]

        blocks = page.get_text(
            "dict",
            clip=clip,
            flags=fitz.TEXTFLAGS_TEXT,
            sort=True,
        )["blocks"]

        for block in blocks:  # iterate textblocks
            previous_y = 0
            for line in block["lines"]:  # iterate lines in block
                if line["dir"][1] != 0:  # only consider horizontal lines
                    continue
                spans = [s for s in line["spans"]]

                this_y = line["bbox"][3]  # current bottom coord

                # check for still being on same line
                same_line = abs(this_y - previous_y) <= 3 and previous_y > 0

                if same_line and out_string.endswith("\n"):
                    out_string = out_string[:-1]

                # are all spans in line in a mono-spaced font?
                all_mono = all([s["flags"] & 8 for s in spans])

                # compute text of the line
                text = "".join([s["text"] for s in spans])
                if not same_line:
                    previous_y = this_y
                    if not out_string.endswith("\n"):
                        out_string += "\n"

                if all_mono:
                    # compute approx. distance from left - assuming a width
                    # of 0.5*fontsize.
                    delta = int(
                        (spans[0]["bbox"][0] - block["bbox"][0])
                        / (spans[0]["size"] * 0.5)
                    )
                    if not code:  # if not already in code output  mode:
                        out_string += "```"  # switch on "code" mode
                        code = True
                    if not same_line:  # new code line with left indentation
                        out_string += "\n" + " " * delta + text + " "
                        previous_y = this_y
                    else:  # same line, simply append
                        out_string += text + " "
                    continue  # done with this line

                for i, s in enumerate(spans):  # iterate spans of the line
                    # this line is not all-mono, so switch off "code" mode
                    if code:  # still in code output mode?
                        out_string += "```\n"  # switch of code mode
                        code = False
                    # decode font properties
                    mono = s["flags"] & 8
                    bold = s["flags"] & 16
                    italic = s["flags"] & 2

                    if mono:
                        # this is text in some monospaced font
                        out_string += f"`{s['text'].strip()}` "
                    else:  # not a mono text
                        # for first span, get header prefix string if present
                        if i == 0:
                            hdr_string = hdr_prefix.get_header_id(s)
                        else:
                            hdr_string = ""
                        prefix = ""
                        suffix = ""
                        if hdr_string == "":
                            if bold:
                                prefix = "**"
                                suffix += "**"
                            if italic:
                                prefix += "_"
                                suffix = "_" + suffix

                        ltext = resolve_links(links, s)
                        if ltext:
                            text = f"{hdr_string}{prefix}{ltext}{suffix} "
                        else:
                            text = f"{hdr_string}{prefix}{s['text'].strip()}{suffix} "
                        text = (
                            text.replace("<", "&lt;")
                            .replace(">", "&gt;")
                            .replace(chr(0xF0B7), "-")
                            .replace(chr(0xB7), "-")
                            .replace(chr(8226), "-")
                            .replace(chr(9679), "-")
                        )
                        out_string += text
                previous_y = this_y
                if not code:
                    out_string += "\n"
            out_string += "\n"
        if code:
            out_string += "```\n"  # switch of code mode
            code = False
        return out_string.replace(" \n", "\n")

    hdr_prefix = IdentifyHeaders(doc, pages=pages)

    # extract text from each page
    all_chunks = []
    pbar = trange(len(pages), desc="pages processed")

    tkz = tiktoken.encoding_for_model("gpt-4o")
    for pno in range(len(pages)):
        page = doc[pno]  # get the page from the index
        page_text = write_text(page, page.rect, hdr_prefix)
        if len(tkz.encode(page_text)) < min_size:
            continue

        # only create chunk if there's meaningful text content
        if page_text.strip():
            all_chunks.append(
                Chunk(
                    id=pno,
                    content=f"Page No: {pno + 1}\nPage Text:\n```\n{page_text.strip()}\n```",
                    loc=f"Page: {pno + 1}",
                )
            )
        pbar.update(1)

    pbar.close()
    return all_chunks


async def extract_docx_text(stream, min_size: int = 10) -> List[Chunk]:
    doc = Document(stream)
    chunks = []
    table_id = 0
    para_id = 0
    curr_para_text = ""
    tkz = tiktoken.encoding_for_model("gpt-4o")

    for x in doc.iter_inner_content():
        if isinstance(x, docx.table.Table):
            table = get_table(x)
            if table:
                chunks.append(
                    Chunk(
                        id=len(chunks),
                        content=f"Table No: {table_id}\nTable Text:\n```\n{array_to_markdown(table)}\n```",
                        loc=f"Table: {table_id}",
                    )
                )
                table_id += 1
        elif isinstance(x, docx.text.paragraph.Paragraph):
            paragraph_text = x.text.strip()
            if paragraph_text:
                n_tokens = len(tkz.encode(paragraph_text))
                if n_tokens + len(tkz.encode(curr_para_text)) > 400:
                    chunks.append(
                        Chunk(
                            id=len(chunks),
                            content=f"Paragraph No: {para_id}\n{curr_para_text}\n",
                            loc=f"Paragraph: {para_id}",
                        )
                    )
                    para_id += 1
                    curr_para_text = paragraph_text
                else:
                    curr_para_text += paragraph_text + "\n"

    if curr_para_text:
        chunks.append(
            Chunk(
                id=len(chunks),
                content=f"Paragraph No: {table_id}\n{curr_para_text}\n",
                loc=f"Paragraph: {para_id}",
            )
        )

    return chunks


# helper function


def get_table(table):
    table_rows = []
    for ir, row in enumerate(table.rows):
        row_data = []
        last_item = ""
        for ic, cell in enumerate(row.cells):
            if last_item == cell.text:
                continue
            last_item = cell.text
            row_data.append([cell.text, (ir, ic)])
        if row_data:
            table_rows.append(row_data)
    if table_rows:
        return table_rows


def array_to_markdown(table):
    markdown = ""
    for row in table:
        markdown += "| "
        for item in row:
            if item is None:
                item = ""
            markdown += str(item).strip() + " | "
        markdown += "\n"
    return markdown
