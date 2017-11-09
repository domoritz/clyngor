"""The Answers object"""


import re
from collections import defaultdict

from clyngor import as_pyasp, parsing


class Answers:
    """Proxy to the solver, generated by solving methods like solve.solve
    or inline.ASP.

    Iterable on the answer sets generated by the solver.
    Also expose some answer set formatting tunning.

    """

    def __init__(self, answers:iter, command:str=''):
        """Answer sets must be iterable of (predicate, args)"""
        self._answers = iter(answers)
        self._command = str(command or '')
        self._first_arg_only = False
        self._group_atoms = False
        self._as_pyasp = False
        self._sorted = False
        self._careful_parsing = False
        self._collapse_atoms= False
        self._collapse_args = True
        self._parse_int = True
        self._ignore_args = False

    @property
    def command(self) -> str:  return self._command

    @property
    def first_arg_only(self):
        """Keep only the first argument, and do not enclose it in a tuple."""
        self._first_arg_only = True
        return self

    @property
    def by_predicate(self):
        """Group atoms by predicate. Answer sets are then dict with predicate
        as keys and collection of args as value."""
        self._group_atoms = True
        return self

    @property
    def as_pyasp(self):
        """Return Term and TermSet object offering a pyasp-like interface"""
        self._as_pyasp = True
        return self

    @property
    def sorted(self):
        """Sort the atom (or the args when grouped)"""
        self._sorted = True
        return self

    @property
    def careful_parsing(self):
        """Use robust parser"""
        self._careful_parsing = True
        return self

    @property
    def atoms_as_string(self):
        """All atoms are encoded as ASP strings, left unparsed."""
        self._collapse_atoms = True
        self._collapse_args = True
        return self

    @property
    def int_not_parsed(self):
        """Do not parse the integer arguments, so if an atom have integers
        as arguments, they will be returned as string, not integers.

        """
        self._parse_int = False
        return self

    @property
    def parse_args(self):
        """Parse the arguments as well, so if an atom is argument of another
        one, it will be parsed as any atom instead of being understood
        as a string.

        Will use the robust parser.

        """
        self._careful_parsing = True  # needed to implement the collapse
        self._collapse_atoms = False
        self._collapse_args = False
        return self

    @property
    def no_arg(self):
        """Do not parse arguments, and discard/ignore them.

        """
        self._ignore_args = True
        return self


    def __next__(self):
        return next(iter(self))


    def __iter__(self):
        """Yield answer sets"""
        for answer_set in self._answers:
            answer_set = self._parse_answer(answer_set)
            answer_set = tuple(answer_set)
            yield self._format(answer_set)


    def _parse_answer(self, answer_set:str) -> iter:
        """Yield atoms as (pred, args) according to parsing options"""
        REG_ANSWER_SET = re.compile(r'([a-z][a-zA-Z0-9_]*)(\([^)]+\))?')
        if self._careful_parsing:
            yield from parsing.Parser(
                self._collapse_atoms, self._collapse_args,
                parse_integer=self._parse_int
            ).parse_terms(answer_set)

        else:  # the good ol' split
            current_answer = set()
            for match in REG_ANSWER_SET.finditer(answer_set):
                pred, args = match.groups()
                assert args is None or (args.startswith('(') and args.endswith(')'))
                if args:
                    args = args[1:-1]
                    if not self._collapse_atoms:  # else: atom as string
                        # parse also integers, if asked to
                        args = tuple(
                            (int(arg) if self._parse_int and
                             (arg[1:] if arg.startswith('-') else arg).isnumeric() else arg)
                            for arg in args.split(',')
                        )
                yield pred, args or ()


    def _format(self, answer_set) -> dict or frozenset:
        """Perform the formatting of the answer set according to
        formatting options.

        """
        sorted_tuple = lambda it: tuple(sorted(it))
        builder = sorted_tuple if self._sorted else frozenset
        if self._ignore_args:
            answer_set = (pred for pred, _ in answer_set)
            if self._group_atoms:
                return {pred: frozenset() for pred in answer_set}
            if self._as_pyasp:
                return builder(as_pyasp.Atom(pred, ()) for pred in answer_set)
            return builder(answer_set)
        elif self._first_arg_only:
            answer_set = builder((pred, args[0] if args else ())
                                   for pred, args in answer_set)
        else:
            answer_set = builder((pred, tuple(args))
                                   for pred, args in answer_set)
        # NB: as_pyasp flag behave differently if group_atoms is activated
        if self._group_atoms:
            mapping = defaultdict(set)
            for pred, args in answer_set:
                if self._as_pyasp:
                    args = as_pyasp.Atom(pred, args)
                mapping[pred].add(args)
            return {pred: builder(args) for pred, args in mapping.items()}
        elif self._as_pyasp:
            return builder(as_pyasp.Atom(*atom) for atom in answer_set)
        return answer_set
