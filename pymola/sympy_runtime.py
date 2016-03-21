# do not edit, generated by pymola

from __future__ import print_function, division
import sympy
import sympy.physics.mechanics as mech


class DaeModel(object):

    def __init__(self):
        self.t = sympy.symbols('t')
        self.x = sympy.Matrix([])
        self.u = sympy.Matrix([])
        self.y = sympy.Matrix([])
        self.p = sympy.Matrix([])
        self.c = sympy.Matrix([])
        self.v = sympy.Matrix([])

    def get_fg(self):
        fg_sol = sympy.solve(self.eqs, self.x.diff(self.t))
        f = self.x.diff(self.t).subs(fg_sol)
        g = self.y.subs(fg_sol)
        return f, g

    def linearize(self):
        f, g = self.get_fg()
        A = sympy.Matrix([])
        B = sympy.Matrix([])
        C = sympy.Matrix([])
        D = sympy.Matrix([])
        print('x', self.x, len(self.x))
        print('u', self.u, len(self.u))
        if len(self.x) > 0:
            A = f.jacobian(self.x)
            C = g.jacobian(self.x)
        if len(self.u) > 0:
            B = f.jacobian(self.u)
            D = g.jacobian(self.u)
        return (A, B, C, D)