import requests
from ast import literal_eval

import appdaemon.adbase as adbase
import appdaemon.adapi as adapi
import appdaemon.utils as utils

from appdaemon.appdaemon import AppDaemon

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from functools import wraps


def hass_check(func):
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        self = args[0]
        ns = self._get_namespace(**kwargs)
        plugin = utils.run_coroutine_threadsafe(self, self.AD.plugins.get_plugin_object(ns))
        if plugin is None:
            self.logger.warning("non_existent namespace (%s) specified in call to %s", ns, func.__name__)
            return lambda *args: None
        if not utils.run_coroutine_threadsafe(self, plugin.am_reading_messages()):
            self.logger.warning("Attempt to call Home Assistant while disconnected: %s", func.__name__)
            return lambda *args: None
        else:
            return func(*args, **kwargs)

    return (func_wrapper)


#
# Define an entities class as a descriptor to enable read only access of HASS state
#

class Hass(adbase.ADBase, adapi.ADAPI):
    #
    # Internal
    #

    def __init__(self, ad: AppDaemon, name, logging, args, config, app_config, global_vars):

        # Call Super Classes
        adbase.ADBase.__init__(self, ad, name, logging, args, config, app_config, global_vars)
        adapi.ADAPI.__init__(self, ad, name, logging, args, config, app_config, global_vars)

        self.AD = ad

        #
        # Register specific constraints
        #
        self.register_constraint("constrain_presence")
        self.register_constraint("constrain_input_boolean")
        self.register_constraint("constrain_input_select")

    #
    # Device Trackers
    #

    def get_trackers(self, **kwargs):
        """Returns a list of all device tracker names.

        Args:
            **kwargs (optional): Zero or more keyword arguments.

        Keyword Args:
            namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Examples:
            >>> trackers = self.get_trackers()
            >>> for tracker in trackers:
            >>>     do something

        """
        return (key for key, value in self.get_state("device_tracker", **kwargs).items())

    def get_tracker_details(self, **kwargs):
        """Returns a list of all device trackers and their associated state.

        Args:
            **kwargs (optional): Zero or more keyword arguments.

        Keyword Args:
            namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Examples:
            >>> trackers = self.get_tracker_details()
            >>> for tracker in trackers:
            >>>     do something

        """
        return self.get_state("device_tracker", **kwargs)

    def get_tracker_state(self, entity_id, **kwargs):
        """Gets the state of a tracker.

        Args:
            entity_id (str): Fully qualified entity id of the device tracker to query, e.g.,
                ``device_tracker.andrew``.
           **kwargs (optional): Zero or more keyword arguments.

        Keyword Args:
            namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Returns:
            The values returned depend in part on the
            configuration and type of device trackers in the system. Simpler tracker
            types like ``Locative`` or ``NMAP`` will return one of 2 states:

            -  ``home``
            -  ``not_home``

            Some types of device tracker are in addition able to supply locations
            that have been configured as Geofences, in which case the name of that
            location can be returned.

        Examples:
            >>> trackers = self.get_trackers()
            >>> for tracker in trackers:
            >>>     self.log("{} is {}".format(tracker, self.get_tracker_state(tracker)))

        """
        self._check_entity(self._get_namespace(**kwargs), entity_id)
        return self.get_state(entity_id, **kwargs)

    @utils.sync_wrapper
    async def anyone_home(self, **kwargs):
        """Determines if the house/apartment is occupied.

        A convenience function to determine if one or more person is home. Use
        this in preference to getting the state of ``group.all_devices()`` as it
        avoids a race condition when using state change callbacks for device
        trackers.

        Args:
            **kwargs (optional): Zero or more keyword arguments.

        Keyword Args:
            namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Returns:
            Returns ``True`` if anyone is at home, ``False`` otherwise.

        Examples:
            >>> if self.anyone_home():
            >>>     do something

        """
        state = await self.get_state(**kwargs)
        for entity_id in state.keys():
            thisdevice, thisentity = entity_id.split(".")
            if thisdevice == "device_tracker":
                if state[entity_id]["state"] == "home":
                    return True
        return False

    @utils.sync_wrapper
    async def everyone_home(self, **kwargs):
        """Determine if all family's members at home.

        A convenience function to determine if everyone is home. Use this in
        preference to getting the state of ``group.all_devices()`` as it avoids
        a race condition when using state change callbacks for device trackers.

        Args:
            **kwargs (optional): Zero or more keyword arguments.

        Keyword Args:
            namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Returns:
            Returns ``True`` if everyone is at home, ``False`` otherwise.

        Examples:
            >>> if self.everyone_home():
            >>>    do something

        """
        state = await self.get_state(**kwargs)
        for entity_id in state.keys():
            thisdevice, thisentity = entity_id.split(".")
            if thisdevice == "device_tracker":
                if state[entity_id]["state"] != "home":
                    return False
        return True

    @utils.sync_wrapper
    async def noone_home(self, **kwargs):
        """Determines if the house/apartment is empty.

        A convenience function to determine if no people are at home. Use this
        in preference to getting the state of ``group.all_devices()`` as it avoids
        a race condition when using state change callbacks for device trackers.

        Args:
            **kwargs (optional): Zero or more keyword arguments.

        Keyword Args:
            namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Returns:
            Returns ``True`` if no one is home, ``False`` otherwise.

        Examples:
            >>> if self.noone_home():
            >>>     do something

        """
        state = await self.get_state(**kwargs)
        for entity_id in state.keys():
            thisdevice, thisentity = entity_id.split(".")
            if thisdevice == "device_tracker":
                if state[entity_id]["state"] == "home":
                    return False
        return True

    #
    # Built in constraints
    #

    def constrain_presence(self, value):
        unconstrained = True
        if value == "everyone" and not self.everyone_home():
            unconstrained = False
        elif value == "anyone" and not self.anyone_home():
            unconstrained = False
        elif value == "noone" and not self.noone_home():
            unconstrained = False

        return unconstrained

    def constrain_input_boolean(self, value):
        unconstrained = True
        state = self.get_state()

        values = value.split(",")
        if len(values) == 2:
            entity = values[0]
            desired_state = values[1]
        else:
            entity = value
            desired_state = "on"
        if entity in state and state[entity]["state"] != desired_state:
            unconstrained = False

        return unconstrained

    def constrain_input_select(self, value):
        unconstrained = True
        state = self.get_state()

        values = value.split(",")
        entity = values.pop(0)
        if entity in state and state[entity]["state"] not in values:
            unconstrained = False

        return unconstrained

    #
    # Helper functions for services
    #

    @hass_check
    @utils.sync_wrapper
    async def turn_on(self, entity_id, **kwargs):
        """Turns `on` a Home Assistant entity.

        This is a convenience function for the ``homassistant.turn_on``
        function. It can turn ``on`` pretty much anything in Home Assistant
        that can be turned ``on`` or ``run`` (e.g., `Lights`, `Switches`,
        `Scenes`, `Scripts`, etc.).

        Args:
            entity_id (str): Fully qualified id of the thing to be turned ``on`` (e.g.,
                `light.office_lamp`, `scene.downstairs_on`).
            **kwargs (optional): Zero or more keyword arguments.

         Keyword Args:
             namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Returns:
            None.

        Examples:
            Turn `on` a switch.

            >>> self.turn_on("switch.backyard_lights")

            Turn `on` a scene.

            >>> self.turn_on("scene.bedroom_on")

            Turn `on` a light and set its color to green.

            >>> self.turn_on("light.office_1", color_name = "green")

        """
        namespace = self._get_namespace(**kwargs)
        if "namespace" in kwargs:
            del kwargs["namespace"]
            
        await self._check_entity(namespace, entity_id)
        if kwargs == {}:
            rargs = {"entity_id": entity_id}
        else:
            rargs = kwargs
            rargs["entity_id"] = entity_id
            
        rargs["namespace"] = namespace
        await self.call_service("homeassistant/turn_on", **rargs)

    @hass_check
    @utils.sync_wrapper
    async def turn_off(self, entity_id, **kwargs):
        """Turns `off` a Home Assistant entity.

        This is a convenience function for the ``homassistant.turn_off``
        function. It can turn ``off`` pretty much anything in Home Assistant
        that can be turned ``off`` (e.g., `Lights`, `Switches`, etc.).

        Args:
            entity_id (str): Fully qualified id of the thing to be turned ``off`` (e.g.,
                `light.office_lamp`, `scene.downstairs_on`).
            **kwargs (optional): Zero or more keyword arguments.

         Keyword Args:
             namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Returns:
            None.

        Examples:
            Turn `off` a switch.

            >>> self.turn_off("switch.backyard_lights")

            Turn `off` a scene.

            >>> self.turn_off("scene.bedroom_on")

        """
        namespace = self._get_namespace(**kwargs)
        if "namespace" in kwargs:
            del kwargs["namespace"]
            
        await self._check_entity(namespace, entity_id)
        if kwargs == {}:
            rargs = {"entity_id": entity_id}
        else:
            rargs = kwargs
            rargs["entity_id"] = entity_id

        rargs["namespace"] = namespace
        device, entity = self.split_entity(entity_id)
        if device == "scene":
            await self.call_service("homeassistant/turn_on", **rargs)
        else:
            await self.call_service("homeassistant/turn_off", **rargs)

    @hass_check
    @utils.sync_wrapper
    async def toggle(self, entity_id, **kwargs):
        """Toggles between ``on`` and ``off`` for the selected entity.

        This is a convenience function for the ``homassistant.toggle`` function.
        It is able to flip the state of pretty much anything in Home Assistant
        that can be turned ``on`` or ``off``.

        Args:
            entity_id (str): Fully qualified id of the thing to be turned ``off`` (e.g.,
                `light.office_lamp`, `scene.downstairs_on`).
            **kwargs (optional): Zero or more keyword arguments.

         Keyword Args:
             namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Returns:
            None.

        Examples:
            >>> self.toggle("switch.backyard_lights")
            >>> self.toggle("light.office_1", color_name = "green")

        """
        namespace = self._get_namespace(**kwargs)
        if "namespace" in kwargs:
            del kwargs["namespace"]
            
        await self._check_entity(namespace, entity_id)
        if kwargs == {}:
            rargs = {"entity_id": entity_id}
        else:
            rargs = kwargs
            rargs["entity_id"] = entity_id
            
        rargs["namespace"] = namespace
        await self.call_service("homeassistant/toggle", **rargs)

    @hass_check
    @utils.sync_wrapper
    async def set_value(self, entity_id, value, **kwargs):
        """Sets the value of an `input_number`.

        This is a convenience function for the ``input_number.set_value``
        function. It can set the value of an ``input_number`` in Home Assistant.

        Args:
            entity_id (str): Fully qualified id of `input_number` to be changed (e.g.,
                `input_number.alarm_hour`).
            value (int or float): The new value to set the `input_number` to.
            **kwargs (optional): Zero or more keyword arguments.

         Keyword Args:
             namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Returns:
            None.

        Examples:
            >>> self.set_value("input_number.alarm_hour", 6)

        """
        namespace = self._get_namespace(**kwargs)
        if "namespace" in kwargs:
            del kwargs["namespace"]
            
        await self._check_entity(namespace, entity_id)
        if kwargs == {}:
            rargs = {"entity_id": entity_id, "value": value}
        else:
            rargs = kwargs
            rargs["entity_id"] = entity_id
            rargs["value"] = value
        rargs["namespace"] = namespace
        await self.call_service("input_number/set_value", **rargs)

    @hass_check
    @utils.sync_wrapper
    async def set_textvalue(self, entity_id, value, **kwargs):
        """Sets the value of an `input_text`.

        This is a convenience function for the ``input_text.set_value``
        function. It can set the value of an `input_text` in Home Assistant.

        Args:
            entity_id (str): Fully qualified id of `input_text` to be changed (e.g.,
                `input_text.text1`).
            value (str): The new value to set the `input_text` to.
            **kwargs (optional): Zero or more keyword arguments.

         Keyword Args:
             namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Returns:
            None.

        Examples:
            >>> self.set_textvalue("input_text.text1", "hello world")

        """
        namespace = self._get_namespace(**kwargs)
        if "namespace" in kwargs:
            del kwargs["namespace"]
            
        await self._check_entity(namespace, entity_id)
        if kwargs == {}:
            rargs = {"entity_id": entity_id, "value": value}
        else:
            rargs = kwargs
            rargs["entity_id"] = entity_id
            rargs["value"] = value
            
        rargs["namespace"] = namespace
        await self.call_service("input_text/set_value", **rargs)

    @hass_check
    @utils.sync_wrapper
    async def select_option(self, entity_id, option, **kwargs):
        """Sets the value of an `input_option`.

        This is a convenience function for the ``input_select.select_option``
        function. It can set the value of an `input_select` in Home Assistant.

        Args:
            entity_id (str): Fully qualified id of `input_select` to be changed (e.g.,
                `input_select.mode`).
            option (str): The new value to set the `input_select` to.
            **kwargs (optional): Zero or more keyword arguments.

         Keyword Args:
             namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Returns:
            None.

        Examples:
            >>> self.select_option("input_select.mode", "Day")

        Todo:
            * Is option always a str?

        """
        namespace = self._get_namespace(**kwargs)
        if "namespace" in kwargs:
            del kwargs["namespace"]
            
        await self._check_entity(namespace, entity_id)
        if kwargs == {}:
            rargs = {"entity_id": entity_id, "option": option}
        else:
            rargs = kwargs
            rargs["entity_id"] = entity_id
            rargs["option"] = option
            
        rargs["namespace"] = namespace
        await self.call_service("input_select/select_option", **rargs)

    @hass_check
    @utils.sync_wrapper
    async def notify(self, message, **kwargs):
        """Sends a notification.

        This is a convenience function for the ``notify.notify`` service. It
        will send a notification to a named notification service. If the name is
        not specified, it will default to ``notify/notify``.

        Args:
            message (str): Message to be sent to the notification service.
            **kwargs (optional): Zero or more keyword arguments.

         Keyword Args:
             title (str, optional): Title of the notification.
             name (str, optional): Name of the notification service.
             namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Returns:
            None.

        Examples:
            >>> self.notify("Switching mode to Evening")
            >>> self.notify("Switching mode to Evening", title = "Some Subject", name = "smtp")

        """
        kwargs["message"] = message
        if "name" in kwargs:
            service = "notify/{}".format(kwargs["name"])
            del kwargs["name"]
        else:
            service = "notify/notify"

        await self.call_service(service, **kwargs)

    @hass_check
    @utils.sync_wrapper
    async def persistent_notification(self, message, title=None, id=None):
        """

        Args:
            message:
            title:
            id:

        Returns:

        Todo:
            * Finish

        """
        kwargs = {}
        kwargs["message"] = message
        if title is not None:
            kwargs["title"] = title
        if id is not None:
            kwargs["notification_id"] = id
        await self.call_service("persistent_notification/create", **kwargs)

    @hass_check
    @utils.sync_wrapper
    async def get_history(self, entity_id = "", **kwargs):
        """Gets access to the HA Database.

        This is a convenience function that allows accessing the HA Database, so the
        history state of a device can be retrieved. It allows for a level of flexibility
        when retrieving the data, and returns it as a dictionary list. Caution must be
        taken when using this, as depending on the size of the database, it can take
        a long time to process.

        Args:
            entity_id (str): Fully qualified id of the device to be querying, e.g.,
                ``light.office_lamp`` or ``scene.downstairs_on`` This can be any entity_id
                in the database. If this is left empty, the state of all entities will be
                retrieved within the specified time. If both ``end_time`` and ``start_time``
                explained below are declared, and ``entity_id`` is specified, the specified
                ``entity_id`` will be ignored and the history states of `all` entity_id in
                the database will be retrieved within the specified time.
            **kwargs (optional): Zero or more keyword arguments.

        Keyword Args:
            days (int, optional): The days from the present-day walking backwards that is
                required from the database.
            start_time (optional): The start time from when the data should be retrieved.
                This should be the furthest time backwards, like if we wanted to get data from
                now until two days ago. Your start time will be the last two days datetime.
                ``start_time`` time can be either a UTC aware time string like ``2019-04-16 12:00:03+01:00``
                or a ``datetime.datetime`` object.
            end_time (optional): The end time from when the data should be retrieved. This should
                be the latest time like if we wanted to get data from now until two days ago. Your
                end time will be today's datetime ``end_time`` time can be either a UTC aware time
                string like ``2019-04-16 12:00:03+01:00`` or a ``datetime.datetime`` object. It should
                be noted that it is not possible to declare only ``end_time``. If only ``end_time``
                is declared without ``start_time`` or ``days``, it will revert to default to the latest
                history state. When ``end_time`` is specified, it is not possible to declare ``entity_id``.
                If ``entity_id`` is specified, ``end_time`` will be ignored.
            namespace (str, optional): Namespace to use for the call. See the section on
                `namespaces <APPGUIDE.html#namespaces>`__ for a detailed description.
                In most cases it is safe to ignore this parameter.

        Returns:
            An iterable list of entity_ids and their history state.

        Examples:
            Get device state over the last 5 days.

            >>> data = self.get_history("light.office_lamp", days = 5)

            Get device state over the last 2 days and walk forward.

            >>> import datetime
            >>> from datetime import timedelta
            >>> start_time = datetime.datetime.now() - timedelta(days = 2)
            >>> data = self.get_history("light.office_lamp", start_time = start_time)

            Get device state from yesterday and walk 5 days back.

            >>> import datetime
            >>> from datetime import timedelta
            >>> end_time = datetime.datetime.now() - timedelta(days = 1)
            >>> data = self.get_history(end_time = end_time, days = 5)

        """
        namespace = self._get_namespace(**kwargs)

        if "namespace" in kwargs:
            del kwargs["namespace"]
        
        if entity_id != "":
            await self._check_entity(namespace, entity_id)
        if kwargs == {}:
            rargs = {"entity_id": entity_id}
        else:
            rargs = kwargs
            rargs["entity_id"] = entity_id
            
        rargs["namespace"] = namespace

        result = await self.call_service("database/history", **rargs)
        return result

    @hass_check
    def render_template(self, template, **kwargs):
        """Renders a Home Assistant Template

        Args:
            template (str): The Home Assistant Template to be rendered.

        Keyword Args:
            None.

        Returns:
            The rendered template in a native Python type.

        Examples:
            >>> self.render_template("{{ states('sun.sun') }}")
            Returns (str) above_horizon

            >>> self.render_template("{{ is_state('sun.sun', 'above_horizon') }}")
            Returns (bool) True

            >>> self.render_template("{{ states('sensor.outside_temp') }}")
            Returns (float) 97.2

        """
        namespace = self._get_namespace(**kwargs)

        if "namespace" in kwargs:
            del kwargs["namespace"]

        rargs = kwargs
        rargs["namespace"] = namespace
        rargs["template"] = template

        result = self.call_service("template/render", **rargs)
        try:
            return literal_eval(result)
        except (SyntaxError, ValueError):
            return result
