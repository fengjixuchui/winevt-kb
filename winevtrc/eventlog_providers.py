# -*- coding: utf-8 -*-
"""Windows Event Log providers collector."""

import logging

from winevtrc import resources


class EventLogProvidersCollector(object):
  """Windows Event Log providers collector."""

  _SERVICES_EVENTLOG_KEY_PATH = (
      'HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Services\\EventLog')

  _WINEVT_PUBLISHERS_KEY_PATH = (
      'HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion\\'
      'WINEVT\\Publishers')

  def _CollectEventLogProviders(
      self, services_eventlog_key, winevt_publishers_key):
    """Collects Windows Event Log providers.

    Args:
      services_eventlog_key (dfwinreg.WinRegistryKey): a Services\\EventLog
          Windows Registry.
      winevt_publishers_key (dfwinreg.WinRegistryKey): a WINEVT\\Publishers
          Windows Registry.

    Yields:
      EventLogProvider: an Event Log provider.
    """
    eventlog_providers_per_identifier = {}
    eventlog_providers_per_log_source = {}

    for eventlog_provider in self._CollectEventLogProvidersFromServicesKey(
        services_eventlog_key):
      log_source = eventlog_provider.log_sources[0]

      existing_eventlog_provider = eventlog_providers_per_identifier.get(
          eventlog_provider.identifier, None)
      if existing_eventlog_provider:
        self._UpdateExistingEventLogProvider(
             existing_eventlog_provider, eventlog_provider)
        continue

      if log_source in eventlog_providers_per_log_source:
        logging.warning((
            'Found multiple definitions for Event Log provider: '
            '{0:s}').format(log_source))
        continue

      eventlog_providers_per_log_source[log_source] = eventlog_provider

      if eventlog_provider.identifier:
        eventlog_providers_per_identifier[eventlog_provider.identifier] = (
              eventlog_provider)

    for eventlog_provider in self._CollectEventLogProvidersFromPublishersKeys(
        winevt_publishers_key):
      log_source = eventlog_provider.log_sources[0]

      existing_eventlog_provider = eventlog_providers_per_log_source.get(
          log_source, None)
      if not existing_eventlog_provider:
        existing_eventlog_provider = eventlog_providers_per_identifier.get(
            eventlog_provider.identifier, None)

        if existing_eventlog_provider:
          if log_source not in existing_eventlog_provider.log_sources:
            existing_eventlog_provider.log_sources.append(log_source)

      if existing_eventlog_provider:
        # TODO: handle mismatches where message files don't define a path.

        if not existing_eventlog_provider.event_message_files:
          existing_eventlog_provider.event_message_files = (
              eventlog_provider.event_message_files)
        elif eventlog_provider.event_message_files not in (
            [], existing_eventlog_provider.event_message_files):
          # TODO: check if one only defines a filename while the other a path.
          # ['%systemroot%\\system32\\winhttp.dll'] != ['winhttp.dll']
          logging.warning((
              'Mismatch in event message files of alternate definition: '
              '{0:s} for Event Log provider: {1:s}').format(
                  log_source, ', '.join(
                      existing_eventlog_provider.log_sources)))

        if not existing_eventlog_provider.identifier:
          existing_eventlog_provider.identifier = eventlog_provider.identifier
        elif existing_eventlog_provider.identifier != (
            eventlog_provider.identifier):
          logging.warning((
              'Mismatch in provider identifier of alternate definition: '
              '{0:s} for Event Log provider: {1:s}').format(
                  log_source, ', '.join(
                      existing_eventlog_provider.log_sources)))

      else:
        eventlog_providers_per_log_source[log_source] = eventlog_provider
        eventlog_providers_per_identifier[eventlog_provider.identifier] = (
            eventlog_provider)

    for _, eventlog_provider in sorted(
        eventlog_providers_per_log_source.items()):
      yield eventlog_provider

  def _CollectEventLogProvidersFromPublishersKeys(self, winevt_publishers_key):
    """Collects Windows Event Log providers from a WINEVT publishers key.

    Args:
      winevt_publishers_key (dfwinreg.WinRegistryKey): WINEVT publishers key.

    Yield:
      EventLogProvider: Event Log provider.
    """
    if winevt_publishers_key:
      for guid_key in winevt_publishers_key.GetSubkeys():
        log_source = self._GetValueAsStringFromKey(guid_key, '')

        event_message_files = self._GetValueAsStringFromKey(
            guid_key, 'MessageFileName', default_value='')
        event_message_files = sorted(filter(None, [
            path.strip().lower() for path in event_message_files.split(';')]))

        provider_identifier = guid_key.name.lower()

        eventlog_provider = resources.EventLogProvider(
            '', log_source, provider_identifier)
        eventlog_provider.event_message_files = event_message_files
        yield eventlog_provider

  def _CollectEventLogProvidersFromServicesKey(self, services_eventlog_key):
    """Collects Windows Event Log providers from a services Event Log key.

    Args:
      services_eventlog_key (dfwinreg.WinRegistryKey): services Event Log key.

    Yield:
      EventLogProvider: Event Log provider.
    """
    if services_eventlog_key:
      for log_type_key in services_eventlog_key.GetSubkeys():
        for provider_key in log_type_key.GetSubkeys():
          log_source = provider_key.name
          log_type = log_type_key.name

          category_message_files = self._GetValueAsStringFromKey(
              provider_key, 'CategoryMessageFile', default_value='')
          category_message_files = sorted(filter(None, [
              path.strip().lower()
              for path in category_message_files.split(';')]))

          event_message_files = self._GetValueAsStringFromKey(
              provider_key, 'EventMessageFile', default_value='')
          event_message_files = sorted(filter(None, [
              path.strip().lower() for path in event_message_files.split(';')]))

          parameter_message_files = self._GetValueAsStringFromKey(
              provider_key, 'ParameterMessageFile', default_value='')
          parameter_message_files = sorted(filter(None, [
              path.strip().lower()
              for path in parameter_message_files.split(';')]))

          provider_identifier = self._GetValueAsStringFromKey(
              provider_key, 'ProviderGuid')
          if provider_identifier:
            provider_identifier = provider_identifier.lower()

          eventlog_provider = resources.EventLogProvider(
              log_type, log_source, provider_identifier)
          eventlog_provider.category_message_files = category_message_files
          eventlog_provider.event_message_files = event_message_files
          eventlog_provider.parameter_message_files = parameter_message_files

          yield eventlog_provider

  def _GetValueAsStringFromKey(
      self, registry_key, value_name, default_value=''):
    """Retrieves a value as a string from a Registry value.

    Args:
      registry_key (dfwinreg.WinRegistryKey): Windows Registry key.
      value_name (str): name of the value.
      default_value (Optional[str]): default value.

    Returns:
      str: value or the default value if not available.
    """
    if not registry_key:
      return default_value

    value = registry_key.GetValueByName(value_name)
    if not value:
      return default_value

    return value.GetDataAsObject()

  def _UpdateExistingEventLogProvider(
      self, existing_eventlog_provider, eventlog_provider):
    """Updates an existing Event Log provider.

    Args:
      existing_eventlog_provider (EventLogProvider): existing Event Log
          provider.
      eventlog_provider (EventLogProvider): Event Log provider.
    """
    log_source = eventlog_provider.log_sources[0]
    if log_source not in existing_eventlog_provider.log_sources:
      existing_eventlog_provider.log_sources.append(log_source)

    if not existing_eventlog_provider.category_message_files:
      existing_eventlog_provider.category_message_files = (
          eventlog_provider.category_message_files)
    elif eventlog_provider.category_message_files not in (
        [], existing_eventlog_provider.category_message_files):
      logging.warning((
          'Mismatch in category message files of alternate definition: '
          '{0:s} for Event Log provider: {1:s}').format(
              log_source, ', '.join(existing_eventlog_provider.log_sources)))

    if not existing_eventlog_provider.event_message_files:
      existing_eventlog_provider.event_message_files = (
          eventlog_provider.event_message_files)
    elif eventlog_provider.event_message_files not in (
        [], existing_eventlog_provider.event_message_files):
       # TODO: check if one only defines a filename while the other a path.
       # ['%systemroot%\\system32\\winhttp.dll'] != ['winhttp.dll']
      logging.warning((
          'Mismatch in event message files of alternate definition: '
          '{0:s} for Event Log provider: {1:s}').format(
              log_source, ', '.join(existing_eventlog_provider.log_sources)))

    if not existing_eventlog_provider.parameter_message_files:
      existing_eventlog_provider.parameter_message_files = (
          eventlog_provider.parameter_message_files)
    elif eventlog_provider.parameter_message_files not in (
        [], existing_eventlog_provider.parameter_message_files):
      logging.warning((
          'Mismatch in provider message files of alternate definition: '
          '{0:s} for Event Log provider: {1:s}').format(
              log_source, ', '.join(existing_eventlog_provider.log_sources)))

  def Collect(self, registry):
    """Collects Windows Event Log providers from a Windows Registry.

    Args:
      registry (dfwinreg.WinRegistry): Windows Registry.

    Returns:
      generator[EventLogProvider]: Event Log provider generator.
    """
    services_eventlog_key = registry.GetKeyByPath(
        self._SERVICES_EVENTLOG_KEY_PATH)
    winevt_publishers_key = registry.GetKeyByPath(
        self._WINEVT_PUBLISHERS_KEY_PATH)

    return self._CollectEventLogProviders(
        services_eventlog_key, winevt_publishers_key)
