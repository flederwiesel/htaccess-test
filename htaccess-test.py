#!/usr/bin/env python3

"""Check whether your `.htaccess` files work as expected by checking against a script
containing request URIs and expected status codes and headers for the response."""

# Intended to be used as a script only
# pylint: disable=invalid-name

import argparse
import json
import re
import os
import sys
from dataclasses import dataclass
import requests
from lxml import html
from lxml.etree import XPathEvalError  # pylint: disable=no-name-in-module


VERSION = "0.0.1"

RED = "\033[31m"
GRE = "\033[32m"
YEL = "\033[33m"
NON = "\033[0m"


@dataclass
class ExpectedResponse:
    """Describes the expected response and where it was defined in the file"""

    def __init__(self, line: int, status: int) -> None:
        self.line = line
        self.status = status
        self.headers = {}
        self.data = []


class NoStatusCodeForResponse(RuntimeError):
    """Raised if response does not start with a status code"""

    def __init__(self) -> None:
        raise SyntaxError(
            "No HTTP status code specified for reponse. "
            "This must be the first entry in the reponse section."
        )


class Testcase:
    """Conducts and evaluate tests, holds test data"""

    cookies = {}
    headers = {}

    @dataclass
    class Diff:
        """Stores and formats unexpected test results"""

        def __init__(self, line: int, name: str, expected: str, actual: str) -> None:
            self.line = line
            self.name = name  # None: HTTP status code
            self.expected = expected
            self.actual = actual

        def items(self) -> list:  # list[str]
            """Return unexpected results as array of coloured diff-like lines"""
            items = [f">@ {self.line}:"]

            if self.name:
                if self.name in "=~/":
                    name = ""  # ~ already in `self.expected`
                    actual = ""  # Suppress actual result (may be extensive!)
                else:
                    # Assume Header -> "Header: "
                    name = f"{self.name}: "
                    actual = self.actual

                items += [f"\t{GRE}-{name}{self.expected}{NON}"]

                if self.actual:
                    items += [f"\t{RED}+{name}{actual}{NON}"]
                else:
                    items += [f"\t{RED}+{name}{NON}"]
            else:
                items += [f"\t{GRE}-{self.expected}{NON}"]

                if self.actual:
                    items += [f"\t{RED}+{self.actual}{NON}"]

            return items

    report: list = []  # list[Diff]

    def __init__(self, line: int, uri: str, method=None) -> None:
        self._line = line
        self._uri = uri
        self._method = method.lower()  # as the requests method names ...
        self._responses = []

    def __str__(self) -> str:
        """Format unexpeted results in a diff-like format"""
        items = [f"<@ {self.line}: {self.uri}"]

        for diff in Testcase.report:
            items += diff.items()

        return os.linesep.join(items)

    @property
    def line(self) -> str:
        # pylint: disable=missing-function-docstring
        return self._line

    @property
    def uri(self) -> str:
        # pylint: disable=missing-function-docstring
        return self._uri

    @property
    def method(self) -> str:
        """Return HTTP request method"""
        return self._method

    @property
    def request(self) -> str:
        """Indicate request is being sent"""
        return f"< {self.method.upper()} {self.uri}"

    @property
    def responses(self) -> list:  # -> list[dict]:
        # pylint: disable=missing-function-docstring
        return self._responses

    def addresp(self, line: int, status: int) -> None:
        """Adds expected HTTP status to the response list"""
        self._responses += [ExpectedResponse(line, status)]

    def addheader(self, header: str, content: str) -> None:
        """Adds expected header data to the response list"""
        if not self._responses:
            raise NoStatusCodeForResponse

        self._responses[-1].headers[header] = content

    def adddata(self, content: str) -> None:
        """Adds expected body data to the response list"""
        if not self._responses:
            raise NoStatusCodeForResponse

        self._responses[-1].data += [content]

    def __repr__(self) -> str:
        resp = json.dumps(self._responses, indent=4)
        method = f" ({self._method})" if self._method else "HEAD"

        return f"\033[37;1m{self.uri}\033[m{method} \033[36m{resp}\033[m"

    def execute(self) -> bool:
        """Executes requests and evaluates responses.
        Follows redirections as long as according responses are defined.
        Adds unexpected results to `Testcase.report`"""
        # pylint: disable=too-many-branches
        nocache = {
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
        }

        uri = self.uri

        for expect in self.responses:
            allow_redirects = not self.method == "head"
            method = getattr(requests, self.method)

            resp = method(
                uri,
                headers={**Testcase.headers, **nocache},
                cookies=Testcase.cookies,
                allow_redirects=allow_redirects,
            )

            line = expect.line
            status = expect.status

            if int(resp.status_code) != status:
                Testcase.report += [Testcase.Diff(line, None, status, resp.status_code)]

            for header, content in expect.headers.items():
                if header not in resp.headers:
                    Testcase.report += [Testcase.Diff(line, header, content, None)]
                else:
                    if resp.headers[header] != content:
                        Testcase.report += [
                            Testcase.Diff(line, header, content, resp.headers[header])
                        ]

            for data in expect.data:
                op, expect = data[:1], data[1:]

                if op == "=":
                    if expect not in resp.text:
                        Testcase.report += [Testcase.Diff(line, op, data, resp.text)]
                elif op == "~":
                    if not re.search(expect, resp.text):
                        Testcase.report += [Testcase.Diff(line, op, data, resp.text)]
                elif op == "/":
                    try:
                        doc = html.document_fromstring(resp.text)
                        result = doc.xpath(f"/{expect}")

                        if not result:
                            Testcase.report += [
                                Testcase.Diff(line, op, data, resp.text)
                            ]
                    except XPathEvalError:
                        Testcase.report += [
                            Testcase.Diff(line, op, data, "Invalid XPath")
                        ]

            if Testcase.report:
                return False

            uri = resp.headers["location"] if "location" in resp.headers else None

        return True


class TestSuite:  # pylint: disable=too-few-public-methods
    """Loads test data from file"""

    @classmethod
    def load(cls, filename: str) -> list:  # -> list[dict]:
        """Get a list of test cases from file, each being a dict of
        line number, request and expected response"""

        tests = []
        lineno = 0

        with open(filename, "r", encoding="utf-8") as stream:
            uri = None

            for line in stream:
                lineno += 1
                line = line.strip()

                if line:
                    statement = line[:1]
                    line = line[1:].strip()

                    if statement == "#":
                        # comment
                        continue

                    if statement == "<":
                        # request
                        try:
                            # HEAD http://localhost
                            method, uri = line.split(" ", maxsplit=1)
                            testcase = Testcase(lineno, uri, method)
                        except ValueError:
                            # http://localhost
                            method = "HEAD"
                            uri = line
                            testcase = Testcase(lineno, uri)

                        tests += [testcase]

                    elif statement == ">":
                        # response
                        if (
                            line.startswith("=")
                            or line.startswith("~")
                            or line.startswith("/")
                        ):
                            testcase.adddata(line)
                        else:
                            try:
                                # Content-Type: text/html; charset=UTF-8
                                header, content = line.split(": ")
                                testcase.addheader(header, content)
                            except ValueError:
                                # 301
                                testcase.addresp(lineno, int(line))

                    else:
                        raise SyntaxWarning(lineno)

        return tests


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Output request URI"
    )
    parser.add_argument(
        "-b", "--cookie", action="store_true", help="Send `test=.htaccess` cookie"
    )
    parser.add_argument(
        "-H", "--header", action="store_true", help="Send `X-Test=.htaccess` header"
    )
    parser.add_argument(
        "-A", "--user-agent", type=str, help="Use the specified user agent"
    )

    args, files = parser.parse_known_args()

    for file in files:
        if args.verbose and len(files) > 1:
            print(file)

        if args.cookie:
            Testcase.cookies["X-Test"] = ".htaccess"

        if args.header:
            Testcase.headers["X-Test"] = ".htaccess"

        Testcase.headers["User-Agent"] = (
            args.user_agent if args.user_agent else f"htaccess-test/{VERSION}"
        )

        testsuite = TestSuite.load(file)

        for test in testsuite:
            if args.verbose:
                print(test.request)

            if not test.execute():
                print(test)
                sys.exit(1)
