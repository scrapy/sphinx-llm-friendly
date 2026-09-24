"""
A submodule class file.
"""


class SubmoduleClass:
    """
    A class inside a submodule.

    :param var: Does nothing
    :type var: str
    """

    def __init__(self, var: str):
        self.var = var

    def function(self, param1: int, param2: str) -> None:
        """Do nothing

        This is a dummy function that does not do anything.

        :param param1: Does nothing
        :type param1: int
        :param param2: Does nothing as well
        :type param2: str
        :return: Nothing.
        :rtype: None
        """
