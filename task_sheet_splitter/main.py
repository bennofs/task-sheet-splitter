#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import re
from typing import Iterable, List, Optional
import fitz



PAGE_NUMBER_REGEX = re.compile(r'^(Page|Seite)?\s*[0-9](\s*(of|von)\s*[0-9]*)?\s*$')
class TaskPart:
    """A task part is a slice of a page between to y-coordinates that belongs to the same task."""
    page: fitz.Page
    rect: fitz.Rect

    __slots__ = ("page", "rect")

    @staticmethod
    def from_y_offsets(page, y0, y1) -> TaskPart:
        """Construct a new part from two y offsets specifying lower and upper bounds of a task part."""
        part = TaskPart()
        part.page = page
        part.rect = fitz.Rect(page.rect[0], y0, page.rect[2], y1)
        return part

    @staticmethod
    def split_page(page, block_re):
        """Split a page into tasks by splitting at text blocks matching the given regex."""
        blocks = sorted([b for b in page.get_text_blocks() if block_re.match(b[4])], key=lambda b: b[1])
        prev = page.rect[1]
        for b in blocks:
            margin = 0.2 * abs(b[3] - b[1])
            upper = max(b[1] - margin, page.rect[1])
            yield TaskPart.from_y_offsets(page, prev, upper)
            prev = upper

        yield TaskPart.from_y_offsets(page, prev, page.rect[3])

    def cropped(self) -> Optional[TaskPart]:
        """Return a task part cropped to fit the text blocks, or None if that would leave the part empty."""
        blocks = []
        last_y = None
        for block in sorted(self.page.get_text('blocks', clip=self.rect), key=lambda block: block[1]):
            if last_y and (block[1] - last_y) / self.page.rect.height > 0.05 and PAGE_NUMBER_REGEX.match(block[4]):
                continue
            if not block[4]:
                continue
            last_y = block[1]
            blocks.append(block)

        if sum(len(b[4]) for b in blocks) < 10:
            return

        return TaskPart.from_y_offsets(
            self.page,
            blocks[0][1] - self.page.rect.height*0.005,
            max(b[3] for b in blocks) + self.page.rect.height*0.007,
        )

    def source_rect(self) -> fitz.Rect:
        return self.rect + fitz.Rect(self.page.CropBoxPosition, self.page.CropBoxPosition)



def collect_tasks(doc: fitz.Document, block_re):
    """Return tasks (list of task parts) by parsing a document.

    The document is cut at text blocks matching the `block_re`.
    """
    tasks = []
    for page_idx in range(doc.page_count):
        page = doc[page_idx]

        for i, part in enumerate(TaskPart.split_page(page, block_re)):
            part = part.cropped()
            if not part: continue

            # merge into previous task if a task crosses a page boundary
            if i == 0 and tasks:
                tasks[-1].append(part)
                continue

            tasks.append([part])

    return tasks


def layout_tasks(result, src, tasks: Iterable[List[TaskPart]], landscape=False, grid=False):
    """Copy each task to a new page in the `result` document."""
    xref = 0
    for task in tasks:
        y_offset = 0
        w, h = task[0].page.rect.width, task[0].page.rect.height
        if landscape:
            w, h = h, w
        new_page = result.new_page(-1, w, h)
        for part in task:
            r = part.source_rect()
            shift = w/2 - r.width/2

            xref = new_page.showPDFpage((shift, y_offset, shift + r.width, y_offset + r.height), src, part.page.number, clip=r, reuse_ref=xref)
            y_offset += r.height + 0.007 * part.page.rect.height

        line_offset = 0.01 * h

        if grid:
            cell_size = task[0].page.rect.width / 40
            opacity = 0.3
            start = y_offset + line_offset
            base = start
            while base <= h:
                new_page.draw_line((0, base), (w, base), stroke_opacity=opacity)
                base += cell_size
            base = (w % cell_size) / 2
            while base <= w:
                new_page.draw_line((base,  start), (base, h), stroke_opacity=opacity)
                base += cell_size
            new_page.draw_line((base,  start), (base, h), stroke_opacity=opacity)


BLOCK_REGEX = re.compile("^Exercise [0-9]+\n$|^Aufgabe [0-9]+\n$")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("src", metavar="INPUT")
    parser.add_argument("dst", metavar="DESTINATION")
    parser.add_argument("--landscape", action="store_true")
    parser.add_argument("--no-grid", action="store_false", dest="grid")
    args = parser.parse_args()

    p = fitz.Document(args.src)
    tasks = collect_tasks(p, BLOCK_REGEX)

    result = fitz.Document()
    layout_tasks(result, p, tasks, landscape=args.landscape, grid=args.grid)
    result.save(args.dst, garbage=4)

if __name__ == '__main__':
    main()
