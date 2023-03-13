# SPDX-FileCopyrightText: Copyright (c) 2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# See README.md for detailed information.
#
# html_render is a simple tool that creates e.g. HTML pages.  The idea is that
# content is represented as a list of lists (which is really a tree) which is
# flattened out at the very end, when the page is rendered.  In this way,
# almost any content can be the content of other tags.  For example::
#
#       content = italic("Hello, world!")
#
# content is now a list of ["<i>", "Hello, world!", "</i>"].  Use "append" to
# add to that content:
#
#       content.append("This is normal")
#       content.append(bold("This is bold"))
#
# content is now ["<i>", "Hello, world!", "</i>", "This is normal", ["<b>",
# "This is bold", "</b>"]].  To make a well-formed HTML page out of this:
#
#       doc = html(body(content))
#
# doc is now ["<html>", ["<body>", ["<i>", "Hello, world!", "</i>", "This is
# normal", ["<b>", "This is bold", "</b>"]], "</body>"], "</html>"] The flatten
# routine adds each element from the given tree as found by a depth-first
# traversal:
#
#       l = flatten([], doc)
#
# l is now ["<html>", "<body>", "<i>", "Hello, world!", "</i>", "This is
# normal", "<b>", "This is bold", "</b>", "</body>", "</html>"].  More commonly,
# use render to flatten then join the results into a single string:
#
#       r = render(doc)
#
# r is now
# "<html><body><i>Hello, world!</i>This is normal<b>This is bold</b></body></html>"
# Note that render(l) and render(doc) produce the same result,
# because render does a flatten step first, which would have no effect on
# an already-flattened list.
#

from html import escape
import yaml


#
# HTML Support
#
def flatten(r, tree):
    """Given a tree, append to list r the elements in a depth-first traversal.
    Application code doesn't normally call this method; just use render.
    """
    for element in tree:
        if hasattr(element, "html"):
            v = element.html()
            flatten(r, v)
            continue
        if isinstance(element, list):
            flatten(r, element)
        else:
            r.append(str(element))
    return r


def render(tree):
    """Flatten the given tree then return it, joined together into a single
    string.
    """
    out = "".join(flatten([], tree))
    return out


def tag(tag_name, style=None, attributes=None):
    """Return content for "<tag attribute(s)... style=style(s)...>"
    with the given elements from the maps for style or attributes.
    style or attributes can be None or {}, in which case
    the relevant section is omitted.
    """
    r = ["<", tag_name]
    if (attributes is not None) and len(attributes):
        for k, v in attributes.items():
            if v is None:
                r.append(" %s" % k)
            else:
                r.append(' %s="%s"' % (k, escape(v)))
    if (style is not None) and len(style):
        r.append(' style="')
        r.append(";".join("%s:%s" % (k, v) for k, v in style.items()))
        r.append('"')
    r.append(">")
    return r


def link(content, url, style=None, attributes=None):
    href = dict(attributes) if attributes is not None else {}
    href["href"] = url
    return [tag("a", style=style, attributes=href), content, "</a>"]


def paragraph(content, style=None):
    return [tag("p", style=style), content, "</p>"]


def horizontal_rule():
    return "<hr/>"


def pre(content, style=None):
    return [tag("pre", style=style), content, "</pre>"]


def italic(content):
    return ["<i>", content, "</i>"]


def bold(content):
    return ["<b>", content, "</b>"]


# Stop chrome from trying to translate from Maltese
default_html_attributes = {
    "lang": "en-US",
}


def html_start(attributes=default_html_attributes):
    return [tag("html", attributes=attributes)]


def html_end():
    return ["</html>"]


def html(content, attributes=default_html_attributes):
    return [html_start(attributes), content, html_end()]


def body_start(attributes={}):
    return [tag("body", attributes=attributes)]


def body_end():
    return ["</body>"]


def body(content, attributes={}):
    return [body_start(attributes), content, body_end()]


def ul(items):
    r = ["<ul>"]
    for i in items:
        r.append(["<li>", i, "</li>"])
    r.append("</ul>")
    return r


def header(level, content, style=None, attributes=None):
    return [
        tag("h%s" % level, style=style, attributes=attributes),
        content,
        "</h%s>" % level,
    ]


default_col_style = {
    "border": "1px solid #CCCCCC",
    "padding-left": "5px",
    "padding-right": "5px",
}
default_table_style = {
    "border-collapse": "collapse",
}


def table(
    rows, style=default_table_style, col_style=default_col_style, attributes=None
):
    r = []
    for cols in rows:
        this_row = [[tag("td", col_style), c, "</td>"] for c in cols]
        r.append([tag("tr"), this_row, "</tr>"])
    return [tag("table", style=style, attributes=attributes), r, "</table>"]


def div(content, style=None, attributes=None):
    return [tag("div", style=style, attributes=attributes), content, "</div>"]


def script(content, style=None, attributes=None):
    return [tag("script", style=style, attributes=attributes), content, "</script>"]


def javascript(content, style=None, attributes={}):
    u = {"type": "text/javascript", "charset": "utf-8"}
    u.update(attributes)
    return script(content, style, u)


def checkbox(content, style=None, attributes={}):
    t = {
        "type": "checkbox",
    }
    t.update(attributes)
    return [
        tag("label"),
        tag("input", style=style, attributes=t),
        content,
        "</label>",
    ]


def _option(value, content, attributes={}):
    n = {}
    n.update(attributes)
    n.update({"value": value})
    return [
        tag("option", attributes=n),
        content,
        "</option>",
    ]


def select(name, options, style=None, attributes={}):
    options = [_option(value, content) for value, content in options.items()]
    return [
        tag("select", style=style, attributes=attributes),
        options,
        "</select>",
    ]


def _rtable(m):
    """Do a depth-first search of m, returning a list of rows for all
    name/value pairs found in m.  If a particular value is a dict, then
    recursively call _rtable on that value, then add the first row from that
    with a new td showing the current name, rowspan'd for the length of the
    inner table; then extend the current row list with the inner list.  IOW
    you'll get a list returned with one element for each row, with extra
    columns (with appropriate rowspans) to serve as headers as appropriate.
    """
    rows = []
    for name, value in m.items():
        if isinstance(value, dict):
            ir = _rtable(value)
            if len(ir):
                h = tag("td", default_col_style, attributes={"rowspan": "%d" % len(ir)})
                this_row = [h, name, "</td>", ir[0]]
                rows.append(this_row)
                rows.extend(ir[1:])
            continue
        elif isinstance(value, list):
            for n, v in enumerate(value):
                ir = _rtable(v)
                h = tag("td", default_col_style, attributes={"rowspan": "%d" % len(ir)})
                this_row = [h, "%s %s" % (name, n), "</td>", ir[0]]
                rows.append(this_row)
                rows.extend(ir[1:])
            continue
        this_row = [[tag("td", default_col_style), c, "</td>"] for c in (name, value)]
        rows.append(this_row)
    return rows


def rtable(m):
    """Given a multi-level map, e.g. {"a": {"b": "YES", "c": "NO"}}, produces an HTML
    table where the higher level keys ("a" in this case) will rowspan in front
    of the lower levels in the map ("b" and "c").
    """
    rows = [[tag("tr"), this_row, "</tr>"] for this_row in _rtable(m)]
    table = [tag("table", style=default_table_style), rows, "</table>"]
    return table


def head(content):
    return [
        tag("head"),
        content,
        "</head>",
    ]


def style(element, options):
    nv = ["%s:%s;" % (k, v) for k, v in options.items()]
    return [
        tag("style"),
        "%s {" % element,
        nv,
        "}",
        "</style>",
    ]


#
# Test report support
#
def na(context, style=None):
    return paragraph(
        italic(
            "N/A: %s" % context,
        ),
        style,
    )


class Div:
    def __init__(self, content=[], style=None, attributes=None):
        self._content = content
        self._style = style
        self._attributes = attributes

    def html(self):
        return div(self._content, style=self._style, attributes=self._attributes)

    def __str__(self):
        return "%s" % self._content

    def yaml(self, dumper):
        return dumper.represent_data(self._content)


yaml.add_representer(Div, lambda dumper, data: data.yaml(dumper))


class Link:
    def __init__(self, content, url, style=None, attributes=None):
        self._content = content
        self._url = url
        self._style = style
        self._attributes = attributes

    def html(self):
        return link(
            self._content, self._url, style=self._style, attributes=self._attributes
        )

    def __str__(self):
        return "%s" % self._content

    def yaml(self, dumper):
        return dumper.represent_data(self._content)


yaml.add_representer(Link, lambda dumper, data: data.yaml(dumper))

# Include this guy in your doc to pull in websocket support.
socket_io_js = script(
    attributes={
        "src": "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js",
        "integrity": "sha512-q/dWJ3kcmjBLU4Qc47E4A9kTB4m3wuTY7vkFJDTZKjTs8jhyGQnaUrxa0Ytd0ssMZhbNua9hE+E7Qv1j+DyZwA==",
        "crossorigin": "anonymous",
    },
    content="",
)
