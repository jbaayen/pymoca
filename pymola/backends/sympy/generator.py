from __future__ import print_function, absolute_import, division, print_function, unicode_literals

import copy
import os
from typing import List

import jinja2

from pymola import ast
from pymola.tree import TreeListener, TreeWalker, flatten

FILE_DIR = os.path.dirname(os.path.realpath(__file__))
# noinspection PyUnresolvedReferences
BUILTINS = dir(__builtins__) + ['psi']


class SympyGenerator(TreeListener):
    def __init__(self):
        super(SympyGenerator, self).__init__()
        self.src = {}

    def exitFile(self, tree: ast.File):
        d = {'classes': []}
        for key in sorted(tree.classes.keys()):
            d['classes'] += [self.src[tree.classes[key]]]

        template = jinja2.Template('''
# do not edit, generated by pymola

from __future__ import print_function, division
import sympy
import sympy.physics.mechanics as mech
from pymola.backends.sympy.runtime import OdeModel
from sympy import sin, cos, tan
{%- for class_key, class in tree.classes.items() %}
{{ render.src[class] }}
{%- endfor %}
''')
        self.src[tree] = template.render({
            'tree': tree,
            'render': self,
        })

    def exitClass(self, tree: ast.Class):
        states = []
        inputs = []
        outputs = []
        constants = []
        parameters = []
        variables = []

        symbols = sorted(tree.symbols.values(), key=lambda x: x.order)  # type: List[ast.Symbol]

        for s in symbols:

            if len(s.prefixes) == 0:
                variables += [s]
            else:
                for prefix in s.prefixes:
                    if prefix == 'state':
                        states += [s]
                    elif prefix == 'constant':
                        constants += [s]
                    elif prefix == 'parameter':
                        parameters += [s]
                    elif prefix == 'input':
                        inputs += [s]
                    elif prefix == 'output':
                        outputs += [s]

        for s in outputs:
            if s not in states:
                variables += [s]

        states_str = ', '.join([self.src[s] for s in states])
        inputs_str = ', '.join([self.src[s] for s in inputs])
        outputs_str = ', '.join([self.src[s] for s in outputs])
        constants_str = ', '.join([self.src[s] for s in constants])
        parameters_str = ', '.join([self.src[s] for s in parameters])
        variables_str = ', '.join([self.src[s] for s in variables])

        d = locals()
        d.pop('self')
        d['render'] = self

        template = jinja2.Template('''

class {{tree.name}}(OdeModel):

    def __init__(self):

        super({{tree.name}}, self).__init__()

        # states
        {% if states_str|length > 0 -%}
        {{ states_str }} = mech.dynamicsymbols('{{ states_str|replace('__', '.') }}')
        {% endif -%}
        self.x = sympy.Matrix([{{ states_str }}])
        self.x0 = {
            {% for s in states -%}
            {{render.src[s]}} : {{tree.symbols[s.name].value.value if tree.symbols[s.name].value.value else tree.symbols[s.name].start.value}},
            {% endfor -%}}

        # variables
        {% if variables_str|length > 0 -%}
        {{ variables_str }} = mech.dynamicsymbols('{{ variables_str|replace('__', '.') }}')
        {% endif -%}
        self.v = sympy.Matrix([{{ variables_str }}])

        # constants
        {% if constants_str|length > 0 -%}
        {{ constants_str }} = sympy.symbols('{{ constants_str|replace('__', '.') }}')
        {% endif -%}
        self.c = sympy.Matrix([{{ constants_str }}])
        self.c0 = {
            {% for s in constants -%}
            {{render.src[s]}} : {{tree.symbols[s.name].value.value if tree.symbols[s.name].value.value else tree.symbols[s.name].start.value}},
            {% endfor -%}}

        # parameters
        {% if parameters_str|length > 0 -%}
        {{ parameters_str }} = sympy.symbols('{{ parameters_str|replace('__', '.') }}')
        {% endif -%}
        self.p = sympy.Matrix([{{ parameters_str }}])
        self.p0 = {
            {% for s in parameters -%}
            {{render.src[s]}} : {{tree.symbols[s.name].value.value if tree.symbols[s.name].value.value else tree.symbols[s.name].start.value}},
            {% endfor -%}}

        # inputs
        {% if inputs_str|length > 0 -%}
        {{ inputs_str }} = mech.dynamicsymbols('{{ inputs_str|replace('__', '.') }}')
        {% endif -%}
        self.u = sympy.Matrix([{{ inputs_str }}])
        self.u0 = {
            {% for s in inputs -%}
            {{render.src[s]}} : {{tree.symbols[s.name].value.value if tree.symbols[s.name].value.value else tree.symbols[s.name].start.value}},
            {% endfor -%}}

        # outputs
        {% if outputs_str|length > 0 -%}
        {{ outputs_str }} = mech.dynamicsymbols('{{ outputs_str|replace('__', '.') }}')
        {% endif -%}
        self.y = sympy.Matrix([{{ outputs_str }}])

        # equations
        self.eqs = [
            {% for eq in tree.equations -%}
            {{ render.src[eq] }},
            {% endfor -%}
        ]

        self.compute_fg()
''')
        self.src[tree] = template.render(d)

    def exitExpression(self, tree: ast.Expression):
        op = str(tree.operator)
        n_operands = len(tree.operands)
        if op == 'der':
            src = '({var:s}).diff(self.t)'.format(
                var=self.src[tree.operands[0]])
        elif op in ['*', '+', '-', '/'] and n_operands == 2:
            src = '{left:s} {op:s} {right:s}'.format(
                op=op,
                left=self.src[tree.operands[0]],
                right=self.src[tree.operands[1]])
        elif op in ['+', '-'] and n_operands == 1:
            src = '{op:s} {expr:s}'.format(
                op=op,
                expr=self.src[tree.operands[0]])
        else:
            operand_src = ','.join([self.src[o] for o in tree.operands])
            src = "{tree.operator.name:s}({operand_src:s})".format(**locals())
        self.src[tree] = src

    def exitPrimary(self, tree: ast.Primary):
        val = str(tree.value)
        self.src[tree] = "{:s}".format(val)

    def exitComponentRef(self, tree: ast.ComponentRef):

        # prevent name clash with builtins
        name = tree.name.replace('.', '__')
        while name in BUILTINS:
            name = name + '_'
        self.src[tree] = name

    def exitSymbol(self, tree: ast.Symbol):
        # prevent name clash with builtins
        name = tree.name.replace('.', '__')
        while name in BUILTINS:
            name = name + '_'

        self.src[tree] = name

    def exitEquation(self, tree: ast.Equation):
        self.src[tree] = "{left:s} - ({right:s})".format(
            left=self.src[tree.left],
            right=self.src[tree.right])


def generate(ast_tree: ast.Collection, model_name: str):
    """
    :param ast_tree: AST to generate from
    :param model_name: class to generate
    :return: sympy source code for model
    """
    component_ref = ast.component_ref_from_string(model_name)
    ast_tree_new = copy.deepcopy(ast_tree)
    ast_walker = TreeWalker()
    flat_tree = flatten(ast_tree_new, component_ref)
    sympy_gen = SympyGenerator()
    ast_walker.walk(sympy_gen, flat_tree)
    return sympy_gen.src[flat_tree]
