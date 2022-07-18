from typing import Any, Optional
from .mixins import CheckMixin
from ....utils.health_api import HealthApi, HealthApiCommon


class HealthMixin(CheckMixin, HealthApiCommon):
    """
    HealthMixin extends the Agent Check base with the Health API allowing Agent Checks to start submitting health data.
    """

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        """
        HealthMixin initializes the Agent Check V2 base class and passes the args and kwargs to the super init, and
        declares the health variable which is an Optional[HealthApi] defaulted to None. It is initialized in setup.

        @param args: *Any
        @param kwargs: **Any
        """
        super(HealthMixin, self).__init__(*args, **kwargs)
        # self._get_instance_schema =
        # self.instance =
        self.health = None  # type: Optional[HealthApi]

    def setup(self):  # type: () -> None
        """
        setup is used to initialize the HealthApi and set the health variable to be used in checks.

        @return: None
        """
        super(HealthMixin, self).setup()

        # Initialize the health api
        HealthApiCommon._init_health_api(self)
