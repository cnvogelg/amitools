vamos - Exec Library
====================

``exec.library`` is the AmigaOS kernel: it owns tasks and signals, the memory
allocator, the message ports, the device/library/resource lists, semaphores and
the interrupt vectors. Everything else in the system is built on top of it, so
vamos has to provide a reasonably faithful implementation before any real
program can run.

vamos implements the ``exec.library`` API in Python. The entry point is
:class:`amitools.vamos.lib.ExecLibrary.ExecLibrary`; the actual LVOs are grouped
by topic into mixin classes in :mod:`amitools.vamos.lib.lexec`. This page
describes that layout. For how a library call is trapped and dispatched in
general, see :doc:`architecture` and :doc:`lib`.


Mixin layout
------------

``ExecLibrary`` itself is only a lifecycle shell. It declares the
``ExecLibrary`` structure, initialises the shared state in ``setup_lib`` and
frees it in ``finish_lib``; every LVO lives in one of the topic mixins it
inherits from. The split follows the comment banners of
``amitools/data/fd/exec_lib.fd`` so that a function's home is obvious from its
LVO comment:

.. list-table::
   :header-rows: 1

   * - fd banner
     - module
     - mixin
   * - tasks / signals
     - ``signalfunc.py``
     - ``SignalMixin``
   * - interrupts
     - ``interruptfunc.py``
     - ``InterruptMixin``
   * - tasks
     - ``taskfunc.py``
     - ``TaskMixin``
   * - messages
     - ``msgfunc.py``
     - ``MessageMixin``
   * - lists
     - ``listfunc.py``
     - ``ListMixin``
   * - memory allocation / more memory / cache
     - ``memfunc.py``
     - ``MemoryMixin``
   * - V39 Pool
     - ``poolfunc.py``
     - ``PoolMixin``
   * - module creation
     - ``modfunc.py``
     - ``ModuleMixin``
   * - libraries
     - ``libfunc.py``
     - ``LibraryMixin``
   * - devices
     - ``devicefunc.py``
     - ``DeviceMixin``
   * - resources
     - ``resourcefunc.py``
     - ``ResourceMixin``
   * - private diagnostic support
     - ``rawiofunc.py``
     - ``RawIOMixin``
   * - signal semaphores
     - ``semaphorefunc.py``
     - ``SemaphoreMixin``
   * - misc / diagnostics
     - ``miscfunc.py``
     - ``MiscMixin``

The ``ExecLibrary`` MRO places all mixins before ``LibImpl``, so the scanner in
:mod:`amitools.vamos.libcore.impl` sees each LVO as a normal method of the
library. ``fd`` arguments are still declared as type-hinted parameters
(``def OpenDevice(self, ctx, dev_name: CSTR, unit, io_request, flags)``): the
lib stub reads the matching registers and converts the value, and a plain
``(self, ctx)`` method reads ``ctx.cpu`` by hand. Keep the type hints intact
when moving a function between mixins.

Most topic mixins share a small base, ``FuncBaseMixin`` in ``funcbase.py``,
which provides the current-task accessors (``get_my_ami_task`` /
``get_my_sched_task``) and the ``get_callee_pc`` call-stub log helper. The
list/module/library/resource/raw-io/semaphore/misc mixins are stateless and do
not need it.


Shared state
------------

``ExecLibrary.setup_lib`` owns everything the mixins read back through
``self``:

- ``ctx`` -- the library call context (also stored on ``ctx.exec_lib``).
- ``exec_lib`` -- the in-memory ``ExecLibrary`` structure (``ExecBase``) with
  its ``mem_list``, ``resource_list``, ``device_list``, ``intr_list``,
  ``lib_list``, ``port_list``, ``task_ready``/``task_wait``,
  ``semaphore_list`` and ``mem_handlers``.
- ``port_mgr`` / ``semaphore_mgr`` -- the Python-side port and semaphore
  registries (``PortManager``, ``SemaphoreManager``).
- ``memory_header`` -- the host heap exposed as an exec ``MemHeader``.
- ``soft_int`` -- the ``SoftIntFunc`` used by ``Cause`` and ``PA_SOFTINT``
  message ports.
- ``_pools`` / ``_poolid`` -- the V39 ``Pool`` registry.
- ``_added_tasks`` -- keeps the ``MappedTask`` objects created by ``AddTask``
  alive while their scheduler task runs.
- ``_io_*`` / ``_msg_port_*`` -- the ``IORequest``/``MsgPort`` field offsets
  cached once for the device LVOs.

The infrastructure helpers in ``lexec/`` are not mixins and are reused by the
mixins or by the rest of vamos: ``PortManager``, ``SemaphoreManager``,
``Pool``/``Puddle``, ``AllocatorMemHeader``, ``Alloc``, ``RawDoFmt``,
``softint``, ``supervisor`` and ``ExecLibCtx``.


Function coverage
-----------------

vamos implements every public ``exec.library`` LVO. The only functions left as
the standard missing-func stubs are the private ``execPrivate1..33`` diagnostic
slots, which are not part of the public API.

The last batch (Stage 2) added the interrupt vectors and servers
(``SetSR`` / ``SuperState`` / ``UserState`` / ``SetIntVector`` /
``AddIntServer`` / ``RemIntServer``), ``AddTask`` / ``RemTask`` and the trap
allocator (``SetExcept`` / ``AllocTrap`` / ``FreeTrap``), the entry/fixed
allocator (``AllocAbs`` / ``AllocEntry`` / ``FreeEntry``) and the memory lists
and handlers (``AddMemList`` / ``AddMemHandler`` / ``RemMemHandler``) plus the
``Cache*`` calls, the semaphore-list and legacy ``Procure`` / ``Vacate``
helpers, ``AddDevice`` / ``RemDevice``, ``AddResource`` / ``RemResource``,
``InitCode`` and the misc/diagnostic calls (``Debug`` / ``GetCC`` /
``ObtainQuickVector`` / ``SumKickData`` / ``ColdReboot`` and ``Child*``).

Fidelity follows a simple rule: real bookkeeping where the guest can see the
state, and an honest, documented stub where the host has no equivalent. In
particular ``AllocAbs`` returns ``NULL`` (the host allocator cannot place a
block at a fixed address), ``AddMemList`` only records the header,
``ObtainQuickVector`` returns ``0`` like AROS (vamos has no quick vectors) so
the caller falls back to a normal interrupt server, ``ColdReboot`` /
``SumKickData`` are no-ops, and the ``Child*`` calls report "no child
registry". ``AddTask`` / ``RemTask`` integrate with the scheduler for the
simple case of an externally built ``Task`` that owns a native m68k stack; the
limits of that mapping are documented in the mixin.

The split is reported by ``test/unit/lib_exec_scan.py``, which scans
``ExecLibrary`` against ``exec_lib.fd``. The test fails on an
*invalid*/*error* function (a method whose signature no longer matches its fd
entry) or if the implemented set shrinks, and it asserts that the only missing
functions are the private ``execPrivate*`` slots.


Adding an LVO
-------------

1. Put the method in the mixin for its fd banner (add a new module + mixin, and
   inherit it in ``ExecLibrary``, when the banner has none yet).
2. Keep the ``(self, ctx, ...)`` signature and the fd type hints.
3. Read any shared state from ``self`` (``self.ctx``, ``self.exec_lib``,
   ``self.port_mgr``, ...) rather than from module globals.
4. Add a unit test that drives the mixin directly with a small host object or
   ``SimpleNamespace`` ctx (see ``test/unit/lib_exec_softint.py``), and a
   ``test/suite`` driver when 68k behaviour matters.
