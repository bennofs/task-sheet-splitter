#!/usr/bin/env python3
import argparse
import sys
import re
import fitz


FMT_REGEX = re.compile("^Exercise [0-9]+\n$|^Aufgabe [0-9]+\n$")
def split_at_block(result, src, page_idx, block_re, landscape=False, grid=False):
    page = src[page_idx]
    blocks = sorted([b for b in page.get_text_blocks() if block_re.match(b[4])], key=lambda b: b[1])
    prev = page.rect[1]
    rects = []
    for b in blocks:
        margin = 0.2 * abs(b[3] - b[1])
        upper = max(b[1] - margin, page.rect[1])
        r = (page.rect[0], prev, page.rect[2], upper)
        prev = upper
        rects.append(r)
    rects.append((page.rect[0], prev, page.rect[2], page.rect[3]))
    xref = 0
    for r in rects:
        w, h = page.rect.width, page.rect.height
        if landscape:
            w, h = h, w
        new_page = result.new_page(-1, w, h)
        r = fitz.Rect(*r)
        r += fitz.Rect(page.CropBoxPosition, page.CropBoxPosition)

        shift = w/2 - r.width/2
        xref = new_page.showPDFpage((shift, 0, shift + r.width, r.height), src, page.number, clip=r, reuse_ref=xref)

        line_offset = 0.01 * h

        if grid:
            cell_size = page.rect.width / 40
            opacity = 0.3
            start = r.height + line_offset
            base = start
            while base <= h:
                new_page.draw_line((0, base), (w, base), stroke_opacity=opacity)
                base += cell_size
            base = (w % cell_size) / 2
            while base <= w:
                new_page.draw_line((base,  start), (base, h), stroke_opacity=opacity)
                base += cell_size
            new_page.draw_line((base,  start), (base, h), stroke_opacity=opacity)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("src", metavar="INPUT")
    parser.add_argument("dst", metavar="DESTINATION")
    parser.add_argument("--landscape", action="store_true")
    parser.add_argument("--no-grid", action="store_false", dest="grid")
    args = parser.parse_args()

    p = fitz.Document(args.src)
    result = fitz.Document()
    split_at_block(result, p, 0, FMT_REGEX, landscape=args.landscape, grid=args.grid)
    result.save(args.dst, garbage=4)

if __name__ == '__main__':
    main()
