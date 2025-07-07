#!/usr/bin/env python3

"""Check whether your `.htaccess` files work as expected by checking against a script
containing request URIs and expected status codes and headers for the response."""

import argparse
import json
import requests
import sys

RED = "\033[31m"
GRE = "\033[32m"
YEL = "\033[33m"
NON = "\033[0m"

class Testcase:
    def __init__(self, line: int, uri: str, method = None):
        self._line = line
        self._uri = uri
        self._method = method.lower() # as the requests method names ...
        self._responses = []

    @property
    def line(self) -> str:
        return self._line

    @property
    def uri(self) -> str:
        return self._uri

    @property
    def method(self) -> str:
        return self._method

    @property
    def request(self):
        return f"< {self.method.upper()} {self.uri}"

    @property
    def responses(self): # -> list[dict]:
        return self._responses

    def addresp(self, line: int, status: int) -> None:
        self._responses += [{"line": line, "status": status}]

    def addheader(self, header: str, content: str) -> None:
        self._responses[-1][header] = content

    def __repr__(self):
        resp = json.dumps(self._responses, indent=4)
        method = f" ({self._method})" if self._method else "HEAD"

        return f"\033[37;1m{self.uri}\033[m{method} \033[36m{resp}\033[m"

    def execute(self):
        diff = []

        uri = self.uri

        for expect in test.responses:
            allow_redirects = False if self.method == "head" else True
            method = getattr(requests, self.method)

            resp = method(uri, allow_redirects=allow_redirects)

            line = expect["line"]
            status = expect["status"]

            if int(resp.status_code) != status:
                diff += [(line, None, status, resp.status_code)]

            del expect["line"]
            del expect["status"]

            for header, content in expect.items():
                if header not in resp.headers:
                    diff += [(line, header, content, None)]
                else:
                    if resp.headers[header] != content:
                        diff += [(line, header, content, resp.headers[header])]

            if diff:
                return diff

            uri = resp.headers["location"] if "location" in resp.headers else None

        return diff

    def report(self, diff):
        print(f"<@ {self.line}: {self.uri}")

        for line, name, expect, result in diff:
            print(f">@ {line}:")

            if name:
                print(f"\t{GRE}-{name}: {expect}{NON}")

                if result:
                    print(f"\t{RED}+{name}: {result}{NON}")
            else:
                print(f"\t{GRE}-{expect}{NON}")

                if result:
                    print(f"\t{RED}+{result}{NON}")

class TestSuite:

    @classmethod
    def load(cls, filename: str): # -> list[dict]:
        """Get a list of test cases from file, each being a dict of
        line number, request and expected response"""

        tests = []
        lineno = 0

        with open(filename, "r", encoding="utf-8") as file:
            uri = None
            responses = []

            for line in file:
                lineno += 1
                line = line.strip()

                if line:
                    statement = line[:1]
                    line = line[1:].strip()

                    if statement == "#":
                        # comment
                        continue

                    elif statement == "<":
                        # request
                        try:
                            # HEAD http://localhost
                            method, uri = line.split(" ", maxsplit=1)
                            test = Testcase(lineno, uri, method)
                        except ValueError:
                            # http://localhost
                            method = "HEAD"
                            uri = line
                            test = Testcase(lineno, uri)

                        tests += [test]

                    elif statement == ">":
                        # response
                        try:
                            # Content-Type: text/html; charset=UTF-8
                            header, content = line.split(": ")
                            test.addheader(header, content)
                        except ValueError:
                            # 301
                            test.addresp(lineno, int(line))

                    else:
                        raise SyntaxWarning(lineno)

        return tests


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--verbose", action="store_true")

    args, files = parser.parse_known_args()

    for file in files:
        if args.verbose and len(files) > 1:
            print(file)

        tests = TestSuite.load(file)

        for test in tests:
            if args.verbose:
                print(test.request)

            diff = test.execute()

            if diff:
                test.report(diff)
                sys.exit(1)
