/// Gestión Deportiva (P2 · CU-09 … CU-17).
///
/// Separa de forma limpia:
/// - Pestaña 0: Gestionar Equipos (CU-09) con CRUD completo (Crear, Ver, Editar, Baja/Reactivar).
/// - Pestaña 1: Indumentaria de Equipo (CU-10) con registro/edición de kits, vista óptica y restablecimiento.
/// - Pestaña 2: Plantel de Jugadores (CU-11) con CRUD completo (Crear, Ver, Editar, Baja/Reactivar).
/// - Pestañas 3 y 4: Partidos (CU-15) y Alineación (CU-17).
library;

import 'package:flutter/material.dart';

import '../../app/tema.dart';
import '../../shared/api/almacenamiento.dart';
import '../../shared/api/cliente.dart';
import 'api.dart';
import 'modelos.dart';
import 'widgets/tarjeta_equipo.dart';
import 'widgets/tarjeta_jugador.dart';

const List<({String nombre, String hex})> _paletaColoresKits = [
  (nombre: 'Celeste Bolívar', hex: '#1E5AA8'),
  (nombre: 'Celeste Cielo', hex: '#4FC3F7'),
  (nombre: 'Azul Marino', hex: '#0F172A'),
  (nombre: 'Azul Real', hex: '#1E40AF'),
  (nombre: 'Blanco Puro', hex: '#FFFFFF'),
  (nombre: 'Amarillo Oro', hex: '#F2C200'),
  (nombre: 'Rojo Escarlata', hex: '#DC2626'),
  (nombre: 'Granate', hex: '#7F1D1D'),
  (nombre: 'Verde Césped', hex: '#15803D'),
  (nombre: 'Verde Lima', hex: '#10B981'),
  (nombre: 'Naranja Fuego', hex: '#EA580C'),
  (nombre: 'Púrpura', hex: '#7E22CE'),
  (nombre: 'Gris Carbón', hex: '#334155'),
  (nombre: 'Negro Azabache', hex: '#18181B'),
];

class DeportivoPagina extends StatefulWidget {
  const DeportivoPagina({super.key});

  @override
  State<DeportivoPagina> createState() => _DeportivoPaginaState();
}

class _DeportivoPaginaState extends State<DeportivoPagina> {
  // 0: Equipos (CU-09), 1: Indumentaria (CU-10), 2: Plantel (CU-11), 3: Partidos (CU-15), 4: Alineación (CU-17)
  int _pestanaActiva = 0;

  List<Equipo> _equipos = [];
  bool _cargando = true;
  String? _error;
  String _busqueda = '';
  String _categoriaSeleccionada = 'Todas';
  bool _mostrarInactivos = false;

  final TextEditingController _controladorBusqueda = TextEditingController();

  // ---------------- Estado de CU-11 · Plantel de Jugadores ----------------
  int? _equipoPlantelId;
  List<Jugador> _jugadores = [];
  bool _cargandoJugadores = false;
  String? _errorJugadores;
  String _busquedaJugadores = '';
  bool _mostrarInactivosJugadores = false;

  final TextEditingController _controladorBusquedaJugadores =
      TextEditingController();

  @override
  void initState() {
    super.initState();
    _inicializarDatos();
  }

  @override
  void dispose() {
    _controladorBusqueda.dispose();
    _controladorBusquedaJugadores.dispose();
    super.dispose();
  }

  Future<void> _inicializarDatos() async {
    final hayToken = await Almacenamiento.haySesion();
    if (!hayToken) {
      try {
        await conectarSesionDemo();
      } catch (_) {
        // Si el backend no está levantado, igual intentaremos cargar desde caché
      }
    }
    await _cargarEquipos();
  }

  Future<void> _cargarEquipos({bool forzarRed = false}) async {
    if (!mounted) return;
    setState(() {
      _cargando = true;
      _error = null;
    });

    try {
      final lista = await listarEquipos(
        activos: !_mostrarInactivos,
        forzarRed: forzarRed,
      );
      if (!mounted) return;
      setState(() {
        _equipos = lista;
        _cargando = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e is ErrorApi
            ? e.detalle
            : 'No se pudo conectar al servidor. Verifica tu conexión o desliza para reintentar.';
        _cargando = false;
      });
    }
  }

  List<String> get _categoriasDisponibles {
    final cats = <String>{'Todas'};
    for (final eq in _equipos) {
      if (eq.categoria.trim().isNotEmpty) {
        cats.add(eq.categoria.trim());
      }
    }
    return cats.toList();
  }

  List<Equipo> get _equiposFiltrados {
    return _equipos.where((eq) {
      final coincideCat = _categoriaSeleccionada == 'Todas' ||
          eq.categoria.toLowerCase() == _categoriaSeleccionada.toLowerCase();
      final q = _busqueda.trim().toLowerCase();
      final coincideTexto = q.isEmpty ||
          eq.nombre.toLowerCase().contains(q) ||
          eq.categoria.toLowerCase().contains(q) ||
          eq.temporada.toLowerCase().contains(q);
      return coincideCat && coincideTexto;
    }).toList();
  }

  // ---------------- Lógica de CU-11 · Plantel de Jugadores ----------------

  Future<void> _asegurarPlantelCargado() async {
    if (_equipos.isEmpty) {
      await _cargarEquipos();
    }
    if (!mounted || _equipos.isEmpty) return;

    final idActual = _equipoPlantelId;
    final existe =
        idActual != null && _equipos.any((eq) => eq.id == idActual);
    if (!existe) {
      _equipoPlantelId = _equipos.first.id;
    }
    await _cargarJugadores();
  }

  Future<void> _cargarJugadores({bool forzarRed = false}) async {
    final equipoId = _equipoPlantelId;
    if (equipoId == null || !mounted) return;

    setState(() {
      _cargandoJugadores = true;
      _errorJugadores = null;
    });

    try {
      final lista = await listarJugadores(
        equipoId,
        activos: !_mostrarInactivosJugadores,
        forzarRed: forzarRed,
      );
      if (!mounted) return;
      setState(() {
        _jugadores = lista;
        _cargandoJugadores = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorJugadores = e is ErrorApi
            ? e.detalle
            : 'No se pudo cargar el plantel. Verifica tu conexión o desliza para reintentar.';
        _cargandoJugadores = false;
      });
    }
  }

  void _seleccionarEquipoPlantel(int nuevoId) {
    if (nuevoId == _equipoPlantelId) return;
    setState(() {
      _equipoPlantelId = nuevoId;
      _jugadores = [];
    });
    _cargarJugadores();
  }

  List<Jugador> get _jugadoresFiltrados {
    final q = _busquedaJugadores.trim().toLowerCase();
    return _jugadores.where((j) {
      if (!_mostrarInactivosJugadores && !j.activo) return false;
      if (q.isEmpty) return true;
      return j.nombreCompleto.toLowerCase().contains(q) ||
          j.dorsal.toString().contains(q);
    }).toList();
  }

  // ---------------- Modales CRUD de CU-09 (Equipos) ----------------

  Future<void> _mostrarFormularioEquipo({Equipo? equipoEditar}) async {
    final formKey = GlobalKey<FormState>();
    final ctrlNombre = TextEditingController(text: equipoEditar?.nombre ?? '');
    final ctrlCategoria = TextEditingController(
        text: equipoEditar?.categoria ?? 'Primera División');
    final ctrlTemporada =
        TextEditingController(text: equipoEditar?.temporada ?? '2026');
    bool guardando = false;
    String? errorLocal;

    final guardado = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) {
          final bottomInset = MediaQuery.of(ctx).viewInsets.bottom;
          return SingleChildScrollView(
            padding: EdgeInsets.fromLTRB(20, 20, 20, 24 + bottomInset),
            child: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    'P2 · CU-09',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1.0,
                      color: verde,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    equipoEditar != null
                        ? 'Editar equipo: ${equipoEditar.nombre}'
                        : 'Registrar nuevo equipo',
                    style: const TextStyle(
                        fontSize: 22, fontWeight: FontWeight.w900),
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: ctrlNombre,
                    textCapitalization: TextCapitalization.words,
                    decoration: const InputDecoration(
                      labelText: 'Nombre del equipo *',
                      hintText: 'Ej. Primera División, Reserva, Sub-19',
                      border: OutlineInputBorder(),
                    ),
                    validator: (v) => (v == null || v.trim().isEmpty)
                        ? 'Ingresa el nombre del equipo'
                        : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: ctrlCategoria,
                    textCapitalization: TextCapitalization.words,
                    decoration: const InputDecoration(
                      labelText: 'Categoría / División',
                      hintText: 'Ej. División Profesional, Sub-17',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: ctrlTemporada,
                    decoration: const InputDecoration(
                      labelText: 'Temporada',
                      hintText: 'Ej. 2026',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  if (errorLocal != null) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFA2372A).withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                            color: const Color(0xFFA2372A), width: 1.5),
                      ),
                      child: Text(
                        errorLocal!,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: Color(0xFFA2372A),
                        ),
                      ),
                    ),
                  ],
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: guardando
                              ? null
                              : () => Navigator.of(ctx).pop(false),
                          style: OutlinedButton.styleFrom(
                            minimumSize: const Size.fromHeight(48),
                          ),
                          child: const Text(
                            'CANCELAR',
                            style: TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: FilledButton(
                          onPressed: guardando
                              ? null
                              : () async {
                                  if (!formKey.currentState!.validate()) return;
                                  setModalState(() {
                                    guardando = true;
                                    errorLocal = null;
                                  });
                                  try {
                                    if (equipoEditar != null) {
                                      await editarEquipo(
                                        equipoEditar.id,
                                        nombre: ctrlNombre.text.trim(),
                                        categoria: ctrlCategoria.text.trim(),
                                        temporada: ctrlTemporada.text.trim(),
                                      );
                                    } else {
                                      await crearEquipo(
                                        nombre: ctrlNombre.text.trim(),
                                        categoria: ctrlCategoria.text.trim(),
                                        temporada: ctrlTemporada.text.trim(),
                                      );
                                    }
                                    if (ctx.mounted) {
                                      Navigator.of(ctx).pop(true);
                                    }
                                  } catch (e) {
                                    setModalState(() {
                                      errorLocal = e is ErrorApi
                                          ? e.detalle
                                          : 'No se pudo guardar el equipo.';
                                      guardando = false;
                                    });
                                  }
                                },
                          style: FilledButton.styleFrom(
                            backgroundColor: verde,
                            minimumSize: const Size.fromHeight(48),
                          ),
                          child: guardando
                              ? const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2.5,
                                    color: Colors.white,
                                  ),
                                )
                              : Text(
                                  equipoEditar != null ? 'GUARDAR' : 'CREAR',
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w800),
                                ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );

    ctrlNombre.dispose();
    ctrlCategoria.dispose();
    ctrlTemporada.dispose();

    if (guardado == true && mounted) {
      await _cargarEquipos();
    }
  }

  Future<void> _confirmarCambioEstadoEquipo(
    Equipo equipo, {
    required bool activar,
  }) async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          activar
              ? '¿Reactivar a ${equipo.nombre}?'
              : '¿Dar de baja a ${equipo.nombre}?',
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        content: Text(
          activar
              ? 'El equipo volverá a estar activo en el club.'
              : 'El equipo pasará a estado inactivo conservando todo su plantel e historial de partidos.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('CANCELAR'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: activar ? verde : const Color(0xFFA2372A),
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(activar ? 'REACTIVAR' : 'DAR DE BAJA'),
          ),
        ],
      ),
    );

    if (confirmar != true || !mounted) return;
    try {
      if (activar) {
        await editarEquipo(equipo.id, activo: true);
      } else {
        await desactivarEquipo(equipo.id);
      }
      await _cargarEquipos();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            e is ErrorApi ? e.detalle : 'No se pudo actualizar el equipo.',
          ),
        ),
      );
    }
  }

  // ---------------- Modales CRUD de CU-10 (Indumentaria) ----------------

  Future<void> _mostrarFormularioIndumentaria(Equipo equipo) async {
    String colorLocal = equipo.colorLocal.toUpperCase();
    String colorVisitante = equipo.colorVisitante.toUpperCase();
    String colorArquero = equipo.colorArquero.toUpperCase();
    int kitSeleccionado = 0; // 0: Local, 1: Visita, 2: Arquero
    bool guardando = false;
    String? errorLocal;

    final guardado = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) {
          final colorActivo = switch (kitSeleccionado) {
            0 => colorLocal,
            1 => colorVisitante,
            _ => colorArquero,
          };

          void asignarColor(String hex) {
            setModalState(() {
              if (kitSeleccionado == 0) {
                colorLocal = hex;
              } else if (kitSeleccionado == 1) {
                colorVisitante = hex;
              } else {
                colorArquero = hex;
              }
            });
          }

          return SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'P2 · CU-10 · INDUMENTARIA OFICIAL',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.0,
                    color: verde,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Configurar Kits: ${equipo.nombre}',
                  style: const TextStyle(
                      fontSize: 21, fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 14),

                // Selector de uniforme a configurar (Titular / Visita / Arquero)
                Row(
                  children: [
                    for (final entry in [
                      (idx: 0, label: 'Titular', hex: colorLocal),
                      (idx: 1, label: 'Alternativa', hex: colorVisitante),
                      (idx: 2, label: 'Arquero', hex: colorArquero),
                    ]) ...[
                      if (entry.idx > 0) const SizedBox(width: 8),
                      Expanded(
                        child: InkWell(
                          onTap: () => setModalState(
                              () => kitSeleccionado = entry.idx),
                          borderRadius: BorderRadius.circular(8),
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                                vertical: 10, horizontal: 8),
                            decoration: BoxDecoration(
                              color: kitSeleccionado == entry.idx
                                  ? verde.withValues(alpha: 0.14)
                                  : Colors.transparent,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(
                                color: kitSeleccionado == entry.idx
                                    ? verde
                                    : Colors.grey.withValues(alpha: 0.4),
                                width: kitSeleccionado == entry.idx ? 2.0 : 1.2,
                              ),
                            ),
                            child: Column(
                              children: [
                                Container(
                                  width: 32,
                                  height: 32,
                                  decoration: BoxDecoration(
                                    color: Equipo.parseHexColor(entry.hex),
                                    shape: BoxShape.circle,
                                    border: Border.all(
                                        color: Colors.black45, width: 1.5),
                                  ),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  entry.label,
                                  style: const TextStyle(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w800),
                                ),
                                Text(
                                  entry.hex,
                                  style: const TextStyle(
                                    fontSize: 11,
                                    fontFamily: 'monospace',
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 16),

                const Text(
                  'SELECCIONA EL COLOR DE LA PALETA OFICIAL',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0.7,
                  ),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    for (final item in _paletaColoresKits)
                      InkWell(
                        onTap: () => asignarColor(item.hex),
                        borderRadius: BorderRadius.circular(8),
                        child: Container(
                          width: 44,
                          height: 44,
                          decoration: BoxDecoration(
                            color: Equipo.parseHexColor(item.hex),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: colorActivo == item.hex
                                  ? verde
                                  : Colors.black38,
                              width: colorActivo == item.hex ? 3.0 : 1.2,
                            ),
                          ),
                          child: colorActivo == item.hex
                              ? Icon(
                                  Icons.check,
                                  color: Equipo.esColorClaro(
                                          Equipo.parseHexColor(item.hex))
                                      ? Colors.black
                                      : Colors.white,
                                )
                              : null,
                        ),
                      ),
                  ],
                ),

                if (errorLocal != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    errorLocal!,
                    style: const TextStyle(
                      color: Color(0xFFA2372A),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],

                const SizedBox(height: 20),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: guardando
                            ? null
                            : () => Navigator.of(ctx).pop(false),
                        style: OutlinedButton.styleFrom(
                          minimumSize: const Size.fromHeight(48),
                        ),
                        child: const Text(
                          'CANCELAR',
                          style: TextStyle(fontWeight: FontWeight.w800),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        onPressed: guardando
                            ? null
                            : () async {
                                setModalState(() {
                                  guardando = true;
                                  errorLocal = null;
                                });
                                try {
                                  await editarEquipo(
                                    equipo.id,
                                    colorLocal: colorLocal,
                                    colorVisitante: colorVisitante,
                                    colorArquero: colorArquero,
                                  );
                                  if (ctx.mounted) {
                                    Navigator.of(ctx).pop(true);
                                  }
                                } catch (e) {
                                  setModalState(() {
                                    errorLocal = e is ErrorApi
                                        ? e.detalle
                                        : 'No se pudo guardar la indumentaria.';
                                    guardando = false;
                                  });
                                }
                              },
                        style: FilledButton.styleFrom(
                          backgroundColor: verde,
                          minimumSize: const Size.fromHeight(48),
                        ),
                        child: const Text(
                          'GUARDAR KITS',
                          style: TextStyle(fontWeight: FontWeight.w800),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );

    if (guardado == true && mounted) {
      await _cargarEquipos();
    }
  }

  Future<void> _confirmarRestablecerIndumentaria(Equipo equipo) async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          '¿Restablecer kits de ${equipo.nombre}?',
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        content: const Text(
          'Los colores volverán a los valores institucionales base: Local #1E5AA8, Visita #FFFFFF y Arquero #F2C200.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('CANCELAR'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: verde),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('RESTABLECER'),
          ),
        ],
      ),
    );

    if (confirmar != true || !mounted) return;
    try {
      await editarEquipo(
        equipo.id,
        colorLocal: '#1E5AA8',
        colorVisitante: '#FFFFFF',
        colorArquero: '#F2C200',
      );
      await _cargarEquipos();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            e is ErrorApi ? e.detalle : 'No se pudo restablecer el kit.',
          ),
        ),
      );
    }
  }

  // ---------------- Modales CRUD de CU-11 (Plantel) ----------------

  Future<void> _mostrarFormularioJugador({Jugador? jugadorEditar}) async {
    final equipoId = _equipoPlantelId ??
        (_equipos.isNotEmpty ? _equipos.first.id : null);
    if (equipoId == null) return;

    final formKey = GlobalKey<FormState>();
    final ctrlNombre =
        TextEditingController(text: jugadorEditar?.nombre ?? '');
    final ctrlApellido =
        TextEditingController(text: jugadorEditar?.apellido ?? '');
    final ctrlDorsal = TextEditingController(
        text: jugadorEditar != null ? '${jugadorEditar.dorsal}' : '');
    final ctrlAltura = TextEditingController(
        text: jugadorEditar != null ? '${jugadorEditar.alturaCm}' : '');
    final ctrlPeso = TextEditingController(
        text: jugadorEditar?.pesoKg != null
            ? '${jugadorEditar!.pesoKg}'
            : '');
    String posicion = jugadorEditar?.posicion ?? 'MED';
    String pie = jugadorEditar?.pieHabil ?? 'DER';
    bool guardando = false;
    String? errorLocal;

    final resultado = await showModalBottomSheet<Jugador>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setModalState) {
            final bottomInset = MediaQuery.of(ctx).viewInsets.bottom;
            return SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(20, 20, 20, 24 + bottomInset),
              child: Form(
                key: formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'P2 · CU-11',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.0,
                        color: verde,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      jugadorEditar != null
                          ? 'Editar jugador: ${jugadorEditar.nombreCompleto}'
                          : 'Nuevo jugador del plantel',
                      style: const TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: ctrlNombre,
                            textCapitalization: TextCapitalization.words,
                            decoration: const InputDecoration(
                              labelText: 'Nombre *',
                              border: OutlineInputBorder(),
                            ),
                            validator: (v) => (v == null || v.trim().isEmpty)
                                ? 'Ingresa el nombre'
                                : null,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: ctrlApellido,
                            textCapitalization: TextCapitalization.words,
                            decoration: const InputDecoration(
                              labelText: 'Apellido *',
                              border: OutlineInputBorder(),
                            ),
                            validator: (v) => (v == null || v.trim().isEmpty)
                                ? 'Ingresa el apellido'
                                : null,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: ctrlDorsal,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                              labelText: 'Dorsal (1-99) *',
                              border: OutlineInputBorder(),
                            ),
                            validator: (v) {
                              final n = int.tryParse((v ?? '').trim());
                              if (n == null || n < 1 || n > 99) {
                                return 'Entre 1 y 99';
                              }
                              return null;
                            },
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: ctrlAltura,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                              labelText: 'Altura (cm) *',
                              border: OutlineInputBorder(),
                            ),
                            validator: (v) {
                              if (v == null || v.trim().isEmpty) {
                                return 'La altura en cm es obligatoria';
                              }
                              final n = int.tryParse(v.trim());
                              if (n == null || n < 140 || n > 220) {
                                return 'Entre 140 y 220 cm';
                              }
                              return null;
                            },
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: DropdownButtonFormField<String>(
                            initialValue: posicion,
                            decoration: const InputDecoration(
                              labelText: 'Posición',
                              border: OutlineInputBorder(),
                            ),
                            items: [
                              for (final e in etiquetasPosicion.entries)
                                DropdownMenuItem(
                                    value: e.key, child: Text(e.value)),
                            ],
                            onChanged: (v) {
                              if (v != null) {
                                setModalState(() => posicion = v);
                              }
                            },
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: DropdownButtonFormField<String>(
                            initialValue: pie,
                            decoration: const InputDecoration(
                              labelText: 'Pie hábil',
                              border: OutlineInputBorder(),
                            ),
                            items: [
                              for (final e in etiquetasPie.entries)
                                DropdownMenuItem(
                                    value: e.key, child: Text(e.value)),
                            ],
                            onChanged: (v) {
                              if (v != null) {
                                setModalState(() => pie = v);
                              }
                            },
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: ctrlPeso,
                      keyboardType:
                          const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(
                        labelText: 'Peso (kg, opcional)',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    if (errorLocal != null) ...[
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: const Color(0xFFA2372A).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                              color: const Color(0xFFA2372A), width: 1.5),
                        ),
                        child: Text(
                          errorLocal!,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFFA2372A),
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 18),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton(
                            onPressed: guardando
                                ? null
                                : () => Navigator.of(ctx).pop(),
                            style: OutlinedButton.styleFrom(
                              minimumSize: const Size.fromHeight(48),
                            ),
                            child: const Text(
                              'CANCELAR',
                              style: TextStyle(fontWeight: FontWeight.w800),
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: FilledButton(
                            onPressed: guardando
                                ? null
                                : () async {
                                    if (!formKey.currentState!.validate()) {
                                      return;
                                    }
                                    setModalState(() {
                                      guardando = true;
                                      errorLocal = null;
                                    });
                                    try {
                                      final pesoTxt = ctrlPeso.text.trim();
                                      final Jugador res;
                                      if (jugadorEditar != null) {
                                        res = await editarJugador(
                                          jugadorEditar.id,
                                          equipoId: equipoId,
                                          nombre: ctrlNombre.text.trim(),
                                          apellido: ctrlApellido.text.trim(),
                                          dorsal:
                                              int.parse(ctrlDorsal.text.trim()),
                                          posicion: posicion,
                                          pieHabil: pie,
                                          alturaCm:
                                              int.parse(ctrlAltura.text.trim()),
                                          pesoKg: pesoTxt.isEmpty
                                              ? null
                                              : double.parse(pesoTxt),
                                        );
                                      } else {
                                        res = await crearJugador(
                                          equipoId,
                                          nombre: ctrlNombre.text.trim(),
                                          apellido: ctrlApellido.text.trim(),
                                          dorsal:
                                              int.parse(ctrlDorsal.text.trim()),
                                          posicion: posicion,
                                          pieHabil: pie,
                                          alturaCm:
                                              int.parse(ctrlAltura.text.trim()),
                                          pesoKg: pesoTxt.isEmpty
                                              ? null
                                              : double.parse(pesoTxt),
                                        );
                                      }
                                      if (ctx.mounted) {
                                        Navigator.of(ctx).pop(res);
                                      }
                                    } catch (e) {
                                      setModalState(() {
                                        errorLocal = e is ErrorApi
                                            ? e.detalle
                                            : 'No se pudo guardar el jugador.';
                                        guardando = false;
                                      });
                                    }
                                  },
                            style: FilledButton.styleFrom(
                              backgroundColor: verde,
                              minimumSize: const Size.fromHeight(48),
                            ),
                            child: Text(
                              jugadorEditar != null
                                  ? 'GUARDAR CAMBIOS'
                                  : 'GUARDAR JUGADOR',
                              style:
                                  const TextStyle(fontWeight: FontWeight.w800),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );

    ctrlNombre.dispose();
    ctrlApellido.dispose();
    ctrlDorsal.dispose();
    ctrlAltura.dispose();
    ctrlPeso.dispose();

    if (resultado != null && mounted) {
      await _cargarJugadores();
    }
  }

  void _mostrarDetalleJugador(Jugador j) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Theme.of(context).colorScheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 52,
                  height: 52,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: verde,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '#${j.dorsal}',
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w900,
                      color: Colors.white,
                    ),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'FICHA DEL FUTBOLISTA (CU-11)',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                          color: verde,
                        ),
                      ),
                      Text(
                        j.nombreCompleto,
                        style: const TextStyle(
                            fontSize: 21, fontWeight: FontWeight.w900),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 10),
            Text(
              'Posición: ${j.posicionLegible} (${j.posicion})',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            Text(
              'Pie hábil: ${j.pieLegible}',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            Text(
              'Altura: ${j.alturaCm} cm${j.pesoKg != null ? " · Peso: ${j.pesoKg} kg" : ""}',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () {
                      Navigator.of(ctx).pop();
                      _mostrarFormularioJugador(jugadorEditar: j);
                    },
                    icon: const Icon(Icons.edit_outlined),
                    label: const Text('EDITAR'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton(
                    style: FilledButton.styleFrom(backgroundColor: verde),
                    onPressed: () => Navigator.of(ctx).pop(),
                    child: const Text('CERRAR'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmarEstadoJugador(
    Jugador j, {
    required bool activar,
  }) async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          activar
              ? '¿Reactivar a ${j.nombreCompleto}?'
              : '¿Dar de baja a ${j.nombreCompleto}?',
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        content: Text(
          activar
              ? 'El jugador volverá a estar activo en el plantel.'
              : 'El jugador pasará a estado de baja conservando sus métricas e historial.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('CANCELAR'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: activar ? verde : const Color(0xFFA2372A),
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(activar ? 'REACTIVAR' : 'DAR DE BAJA'),
          ),
        ],
      ),
    );

    if (confirmar != true || !mounted) return;
    try {
      if (activar) {
        await editarJugador(j.id, equipoId: j.equipoId, activo: true);
      } else {
        await bajaJugador(j.id, equipoId: j.equipoId);
      }
      await _cargarJugadores();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            e is ErrorApi ? e.detalle : 'No se pudo actualizar el jugador.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Gestión Deportiva',
          style: TextStyle(fontWeight: FontWeight.w800),
        ),
        actions: [
          IconButton(
            tooltip: 'Sincronizar ahora',
            icon: const Icon(Icons.sync_rounded),
            onPressed: () => _pestanaActiva == 2
                ? _cargarJugadores(forzarRed: true)
                : _cargarEquipos(forzarRed: true),
          ),
        ],
      ),
      floatingActionButton: _pestanaActiva == 0
          ? FloatingActionButton.extended(
              onPressed: () => _mostrarFormularioEquipo(),
              backgroundColor: verde,
              foregroundColor: Colors.white,
              icon: const Icon(Icons.add),
              label: const Text(
                'Nuevo equipo',
                style: TextStyle(fontWeight: FontWeight.w800),
              ),
            )
          : (_pestanaActiva == 2 && _equipos.isNotEmpty)
              ? FloatingActionButton.extended(
                  onPressed: () => _mostrarFormularioJugador(),
                  backgroundColor: verde,
                  foregroundColor: Colors.white,
                  icon: const Icon(Icons.person_add_alt_1),
                  label: const Text(
                    'Nuevo jugador',
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                )
              : null,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Barra de navegación superior de casos de uso (Equipos CU-09 e Indumentaria CU-10 separados)
          Container(
            decoration: BoxDecoration(
              color: t.colorScheme.surface,
              border: Border(
                bottom: BorderSide(
                  color: t.colorScheme.outlineVariant,
                  width: 1.5,
                ),
              ),
            ),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(
                children: [
                  _PestanaBoton(
                    titulo: 'Equipos',
                    codigo: 'CU-09',
                    activo: _pestanaActiva == 0,
                    onTap: () => setState(() => _pestanaActiva = 0),
                  ),
                  const SizedBox(width: 6),
                  _PestanaBoton(
                    titulo: 'Indumentaria',
                    codigo: 'CU-10',
                    activo: _pestanaActiva == 1,
                    onTap: () => setState(() => _pestanaActiva = 1),
                  ),
                  const SizedBox(width: 6),
                  _PestanaBoton(
                    titulo: 'Plantel',
                    codigo: 'CU-11',
                    activo: _pestanaActiva == 2,
                    onTap: () {
                      setState(() => _pestanaActiva = 2);
                      _asegurarPlantelCargado();
                    },
                  ),
                  const SizedBox(width: 6),
                  _PestanaBoton(
                    titulo: 'Partidos',
                    codigo: 'CU-15',
                    activo: _pestanaActiva == 3,
                    onTap: () => setState(() => _pestanaActiva = 3),
                  ),
                  const SizedBox(width: 6),
                  _PestanaBoton(
                    titulo: 'Alineación',
                    codigo: 'CU-17',
                    activo: _pestanaActiva == 4,
                    onTap: () => setState(() => _pestanaActiva = 4),
                  ),
                ],
              ),
            ),
          ),

          Expanded(
            child: switch (_pestanaActiva) {
              0 => _construirVistaEquipos(),
              1 => _construirVistaIndumentaria(),
              2 => _construirVistaPlantel(),
              int p => _construirVistaCasosPendientes(p),
            },
          ),
        ],
      ),
    );
  }

  // ---------------- Pestaña 0: Gestionar Equipos (CU-09) ----------------

  Widget _construirVistaEquipos() {
    final t = Theme.of(context);
    final esOscuro = t.brightness == Brightness.dark;

    return RefreshIndicator(
      color: verde,
      onRefresh: () => _cargarEquipos(forzarRed: true),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 88),
        children: [
          // Buscador de equipos
          Container(
            decoration: BoxDecoration(
              color: t.colorScheme.surface,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: esOscuro
                    ? const Color(0xFF475569)
                    : const Color(0xFFCBD5E1),
                width: 1.5,
              ),
            ),
            child: TextField(
              controller: _controladorBusqueda,
              onChanged: (val) => setState(() => _busqueda = val),
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
              decoration: InputDecoration(
                hintText: 'Buscar equipo o temporada…',
                hintStyle: TextStyle(
                  fontSize: 16,
                  color: t.colorScheme.outline,
                  fontWeight: FontWeight.w600,
                ),
                prefixIcon: const Icon(Icons.search, size: 24, color: verde),
                suffixIcon: _busqueda.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _controladorBusqueda.clear();
                          setState(() => _busqueda = '');
                        },
                      )
                    : null,
                border: InputBorder.none,
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              ),
            ),
          ),
          const SizedBox(height: 12),

          // Chips de filtrado rápido por categoría
          if (_categoriasDisponibles.length > 1) ...[
            SizedBox(
              height: 40,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: _categoriasDisponibles.length,
                separatorBuilder: (_, _) => const SizedBox(width: 8),
                itemBuilder: (context, idx) {
                  final cat = _categoriasDisponibles[idx];
                  final seleccionado = cat == _categoriaSeleccionada;
                  return ChoiceChip(
                    label: Text(
                      cat.toUpperCase(),
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                        color: seleccionado
                            ? Colors.white
                            : t.colorScheme.onSurface,
                      ),
                    ),
                    selected: seleccionado,
                    selectedColor: verde,
                    backgroundColor: t.colorScheme.surface,
                    side: BorderSide(
                      color: seleccionado
                          ? verde
                          : (esOscuro
                              ? const Color(0xFF475569)
                              : const Color(0xFFCBD5E1)),
                      width: 1.5,
                    ),
                    onSelected: (_) =>
                        setState(() => _categoriaSeleccionada = cat),
                  );
                },
              ),
            ),
            const SizedBox(height: 12),
          ],

          // Cabecera de resultados y toggle de inactivos
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  '${_equiposFiltrados.length} ${_equiposFiltrados.length == 1 ? "EQUIPO" : "EQUIPOS"} DEL CLUB',
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0.8,
                  ),
                ),
              ),
              InkWell(
                onTap: () {
                  setState(() => _mostrarInactivos = !_mostrarInactivos);
                  _cargarEquipos(forzarRed: true);
                },
                child: Padding(
                  padding:
                      const EdgeInsets.symmetric(vertical: 4, horizontal: 4),
                  child: Row(
                    children: [
                      Icon(
                        _mostrarInactivos
                            ? Icons.check_box
                            : Icons.check_box_outline_blank,
                        size: 20,
                        color: verde,
                      ),
                      const SizedBox(width: 4),
                      const Text(
                        'Ver inactivos',
                        style: TextStyle(
                            fontSize: 14, fontWeight: FontWeight.w700),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          if (_cargando && _equipos.isEmpty)
            const Center(
              child: Padding(
                padding: EdgeInsets.symmetric(vertical: 48),
                child: Column(
                  children: [
                    CircularProgressIndicator(color: verde),
                    SizedBox(height: 16),
                    Text(
                      'Cargando equipos…',
                      style:
                          TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              ),
            )
          else if (_error != null && _equipos.isEmpty)
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFFA2372A).withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
                border:
                    Border.all(color: const Color(0xFFA2372A), width: 1.8),
              ),
              child: Column(
                children: [
                  const Icon(Icons.error_outline,
                      size: 36, color: Color(0xFFA2372A)),
                  const SizedBox(height: 10),
                  Text(
                    _error!,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 14),
                  FilledButton(
                    onPressed: () => _cargarEquipos(forzarRed: true),
                    style: FilledButton.styleFrom(backgroundColor: verde),
                    child: const Text('REINTENTAR'),
                  ),
                ],
              ),
            )
          else if (_equiposFiltrados.isEmpty)
            Container(
              padding:
                  const EdgeInsets.symmetric(vertical: 40, horizontal: 20),
              decoration: BoxDecoration(
                color: t.colorScheme.surface,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: t.colorScheme.outlineVariant,
                  width: 1.5,
                ),
              ),
              child: Column(
                children: [
                  const Icon(Icons.shield_outlined,
                      size: 48, color: Color(0xFF74847A)),
                  const SizedBox(height: 12),
                  const Text(
                    'No se encontraron equipos',
                    style:
                        TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                  ),
                ],
              ),
            )
          else
            // Tarjetas limpias de equipos (CU-09) sin saturar con indumentaria
            for (final eq in _equiposFiltrados)
              TarjetaEquipo(
                equipo: eq,
                mostrarIndumentaria: false,
                onTap: () => _mostrarDetalleEquipo(eq),
                onEditar: () => _mostrarFormularioEquipo(equipoEditar: eq),
                onDesactivar: () =>
                    _confirmarCambioEstadoEquipo(eq, activar: false),
                onReactivar: () =>
                    _confirmarCambioEstadoEquipo(eq, activar: true),
                onIrIndumentaria: () {
                  setState(() => _pestanaActiva = 1);
                },
              ),
        ],
      ),
    );
  }

  // ---------------- Pestaña 1: Indumentaria de Equipo (CU-10) ----------------

  Widget _construirVistaIndumentaria() {
    final t = Theme.of(context);
    final esOscuro = t.brightness == Brightness.dark;
    final colorBorde =
        esOscuro ? const Color(0xFF475569) : const Color(0xFFCBD5E1);

    return RefreshIndicator(
      color: verde,
      onRefresh: () => _cargarEquipos(forzarRed: true),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: verde.withValues(alpha: esOscuro ? 0.16 : 0.08),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: verde, width: 1.4),
            ),
            child: const Row(
              children: [
                Icon(Icons.checkroom_rounded, color: verde, size: 26),
                SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'CU-10 · REGISTRO DE INDUMENTARIA DE EQUIPO',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w900,
                          color: verde,
                        ),
                      ),
                      SizedBox(height: 2),
                      Text(
                        'Configura, visualiza o restablece los colores Titular, Alternativa y Arquero de cada división.',
                        style: TextStyle(
                          fontSize: 13.5,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          if (_equipos.isEmpty)
            Container(
              padding:
                  const EdgeInsets.symmetric(vertical: 40, horizontal: 20),
              decoration: BoxDecoration(
                color: t.colorScheme.surface,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: colorBorde, width: 1.5),
              ),
              child: const Column(
                children: [
                  Icon(Icons.checkroom_outlined,
                      size: 48, color: Color(0xFF74847A)),
                  SizedBox(height: 12),
                  Text(
                    'No hay equipos para configurar indumentaria',
                    style:
                        TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
                  ),
                ],
              ),
            )
          else
            for (final eq in _equipos)
              Card(
                margin: const EdgeInsets.only(bottom: 14),
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                  side: BorderSide(color: colorBorde, width: 1.8),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  eq.nombre,
                                  style: const TextStyle(
                                    fontSize: 19,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  '${eq.categoria.isEmpty ? "General" : eq.categoria} · Temp ${eq.temporada}',
                                  style: TextStyle(
                                    fontSize: 13.5,
                                    fontWeight: FontWeight.w700,
                                    color: t.colorScheme.onSurfaceVariant,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: verde.withValues(alpha: 0.14),
                              borderRadius: BorderRadius.circular(6),
                              border: Border.all(color: verde),
                            ),
                            child: const Text(
                              'CU-10',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w900,
                                fontFamily: 'monospace',
                                color: verde,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      _FilaColorDetalle(
                        rol: 'Titular (Local)',
                        color: eq.colorLocalParsed,
                        hex: eq.colorLocal,
                      ),
                      const SizedBox(height: 8),
                      _FilaColorDetalle(
                        rol: 'Alternativa (Visita)',
                        color: eq.colorVisitanteParsed,
                        hex: eq.colorVisitante,
                      ),
                      const SizedBox(height: 8),
                      _FilaColorDetalle(
                        rol: 'Guardameta (Arquero)',
                        color: eq.colorArqueroParsed,
                        hex: eq.colorArquero,
                      ),
                      const SizedBox(height: 12),
                      const Divider(height: 1),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: [
                          TextButton(
                            onPressed: () => _mostrarDetalleEquipo(eq),
                            child: const Text(
                              'Ver ficha',
                              style: TextStyle(fontWeight: FontWeight.w800),
                            ),
                          ),
                          TextButton(
                            onPressed: () => _mostrarFormularioIndumentaria(eq),
                            style: TextButton.styleFrom(foregroundColor: verde),
                            child: const Text(
                              'Editar Kits',
                              style: TextStyle(fontWeight: FontWeight.w800),
                            ),
                          ),
                          TextButton(
                            onPressed: () =>
                                _confirmarRestablecerIndumentaria(eq),
                            style: TextButton.styleFrom(
                                foregroundColor: const Color(0xFFA2372A)),
                            child: const Text(
                              'Restablecer',
                              style: TextStyle(fontWeight: FontWeight.w800),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
        ],
      ),
    );
  }

  void _mostrarDetalleEquipo(Equipo eq) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        eq.nombre,
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: eq.activo ? verde : const Color(0xFFA2372A),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        eq.activo ? 'ACTIVO' : 'INACTIVO',
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w900,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  'Categoría: ${eq.categoria.isEmpty ? "No especificada" : eq.categoria}  ·  Temporada: ${eq.temporada.isEmpty ? "2026" : eq.temporada}',
                  style: const TextStyle(
                      fontSize: 16, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 4),
                Text(
                  'Jugadores activos registrados: ${eq.jugadores}',
                  style: const TextStyle(
                      fontSize: 16, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 16),
                const Divider(),
                const SizedBox(height: 12),
                const Text(
                  'COLORES DE INDUMENTARIA (CU-10)',
                  style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 0.6),
                ),
                const SizedBox(height: 10),
                _FilaColorDetalle(
                  rol: 'Titular (Local)',
                  color: eq.colorLocalParsed,
                  hex: eq.colorLocal,
                ),
                const SizedBox(height: 8),
                _FilaColorDetalle(
                  rol: 'Alternativa (Visita)',
                  color: eq.colorVisitanteParsed,
                  hex: eq.colorVisitante,
                ),
                const SizedBox(height: 8),
                _FilaColorDetalle(
                  rol: 'Guardameta (Arquero)',
                  color: eq.colorArqueroParsed,
                  hex: eq.colorArquero,
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    style: FilledButton.styleFrom(
                      backgroundColor: verde,
                      minimumSize: const Size.fromHeight(48),
                    ),
                    onPressed: () => Navigator.pop(context),
                    child: const Text(
                      'CERRAR FICHA',
                      style:
                          TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  // ---------------- Pestaña 2: Plantel de Jugadores (CU-11) ----------------

  Widget _construirVistaPlantel() {
    final t = Theme.of(context);
    final esOscuro = t.brightness == Brightness.dark;

    return RefreshIndicator(
      color: verde,
      onRefresh: () => _cargarJugadores(forzarRed: true),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 88),
        children: [
          if (_equipos.isEmpty && !_cargando)
            Container(
              padding:
                  const EdgeInsets.symmetric(vertical: 40, horizontal: 20),
              decoration: BoxDecoration(
                color: t.colorScheme.surface,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: t.colorScheme.outlineVariant,
                  width: 1.5,
                ),
              ),
              child: Column(
                children: [
                  const Icon(Icons.shield_outlined,
                      size: 48, color: Color(0xFF74847A)),
                  const SizedBox(height: 12),
                  const Text(
                    'No hay equipos disponibles',
                    style:
                        TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Registra o sincroniza un equipo en la pestaña Equipos para ver su plantel.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 15,
                      color: t.colorScheme.onSurfaceVariant,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            )
          else ...[
            if (_equipos.length > 1) ...[
              Container(
                decoration: BoxDecoration(
                  color: t.colorScheme.surface,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: esOscuro
                        ? const Color(0xFF475569)
                        : const Color(0xFFCBD5E1),
                    width: 1.5,
                  ),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<int>(
                    value: _equipoPlantelId ?? _equipos.first.id,
                    isExpanded: true,
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w700),
                    items: [
                      for (final eq in _equipos)
                        DropdownMenuItem(value: eq.id, child: Text(eq.nombre)),
                    ],
                    onChanged: (val) {
                      if (val != null) _seleccionarEquipoPlantel(val);
                    },
                  ),
                ),
              ),
              const SizedBox(height: 12),
            ],

            Container(
              decoration: BoxDecoration(
                color: t.colorScheme.surface,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: esOscuro
                      ? const Color(0xFF475569)
                      : const Color(0xFFCBD5E1),
                  width: 1.5,
                ),
              ),
              child: TextField(
                controller: _controladorBusquedaJugadores,
                onChanged: (val) => setState(() => _busquedaJugadores = val),
                style:
                    const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
                decoration: InputDecoration(
                  hintText: 'Buscar por nombre o dorsal…',
                  hintStyle: TextStyle(
                    fontSize: 16,
                    color: t.colorScheme.outline,
                    fontWeight: FontWeight.w600,
                  ),
                  prefixIcon:
                      const Icon(Icons.search, size: 24, color: verde),
                  suffixIcon: _busquedaJugadores.isNotEmpty
                      ? IconButton(
                          icon: const Icon(Icons.clear),
                          onPressed: () {
                            _controladorBusquedaJugadores.clear();
                            setState(() => _busquedaJugadores = '');
                          },
                        )
                      : null,
                  border: InputBorder.none,
                  contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 14),
                ),
              ),
            ),
            const SizedBox(height: 12),

            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    '${_jugadoresFiltrados.length} ${_jugadoresFiltrados.length == 1 ? "JUGADOR" : "JUGADORES"} DEL PLANTEL',
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 0.8,
                    ),
                  ),
                ),
                InkWell(
                  onTap: () {
                    setState(() => _mostrarInactivosJugadores =
                        !_mostrarInactivosJugadores);
                    _cargarJugadores();
                  },
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        vertical: 4, horizontal: 4),
                    child: Row(
                      children: [
                        Icon(
                          _mostrarInactivosJugadores
                              ? Icons.check_box
                              : Icons.check_box_outline_blank,
                          size: 20,
                          color: verde,
                        ),
                        const SizedBox(width: 4),
                        const Text(
                          'Ver inactivos',
                          style: TextStyle(
                              fontSize: 14, fontWeight: FontWeight.w700),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),

            if (_cargandoJugadores && _jugadores.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.symmetric(vertical: 48),
                  child: Column(
                    children: [
                      CircularProgressIndicator(color: verde),
                      SizedBox(height: 16),
                      Text(
                        'Cargando plantel…',
                        style: TextStyle(
                            fontSize: 16, fontWeight: FontWeight.w700),
                      ),
                    ],
                  ),
                ),
              )
            else if (_errorJugadores != null && _jugadores.isEmpty)
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: const Color(0xFFA2372A).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                  border:
                      Border.all(color: const Color(0xFFA2372A), width: 1.8),
                ),
                child: Column(
                  children: [
                    const Icon(Icons.error_outline,
                        size: 36, color: Color(0xFFA2372A)),
                    const SizedBox(height: 10),
                    Text(
                      _errorJugadores!,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                          fontSize: 16, fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 14),
                    FilledButton(
                      onPressed: () => _cargarJugadores(forzarRed: true),
                      style: FilledButton.styleFrom(backgroundColor: verde),
                      child: const Text('REINTENTAR'),
                    ),
                  ],
                ),
              )
            else if (_jugadoresFiltrados.isEmpty)
              Container(
                padding:
                    const EdgeInsets.symmetric(vertical: 40, horizontal: 20),
                decoration: BoxDecoration(
                  color: t.colorScheme.surface,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: t.colorScheme.outlineVariant,
                    width: 1.5,
                  ),
                ),
                child: Column(
                  children: [
                    const Icon(Icons.shield_outlined,
                        size: 48, color: Color(0xFF74847A)),
                    const SizedBox(height: 12),
                    const Text(
                      'No se encontraron jugadores',
                      style:
                          TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      _busquedaJugadores.isNotEmpty
                          ? 'Prueba modificando el texto de búsqueda.'
                          : 'No hay jugadores registrados en este equipo.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 15,
                        color: t.colorScheme.onSurfaceVariant,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              )
            else
              for (final j in _jugadoresFiltrados)
                TarjetaJugador(
                  jugador: j,
                  onTap: () => _mostrarDetalleJugador(j),
                  onEditar: () => _mostrarFormularioJugador(jugadorEditar: j),
                  onBaja: () => _confirmarEstadoJugador(j, activar: false),
                  onReactivar: () => _confirmarEstadoJugador(j, activar: true),
                ),
          ],
        ],
      ),
    );
  }

  Widget _construirVistaCasosPendientes(int pestana) {
    final t = Theme.of(context);
    final datos = switch (pestana) {
      3 => (
          paquete: 'P2 · CU-15',
          titulo: 'Agenda de Partidos',
          responsable: 'Susana · Sprint 2',
          desc:
              'Calendario de partidos programados con modo fuera de línea para consulta en cancha sin cobertura celular.'
        ),
      _ => (
          paquete: 'P2 · CU-17',
          titulo: 'Ver Alineación y Formación',
          responsable: 'Araceli · Sprint 2',
          desc:
              'Visualización táctica de los 11 titulares, suplentes y esquema de juego en la pizarra del encuentro.'
        ),
    };

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
      children: [
        Text(
          datos.paquete,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w800,
            color: verde,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          datos.titulo,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 6),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: verde.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: verde),
          ),
          child: Text(
            'Asignado a: ${datos.responsable}',
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: verde,
            ),
          ),
        ),
        const SizedBox(height: 16),
        Text(
          datos.desc,
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: t.colorScheme.onSurfaceVariant,
            height: 1.5,
          ),
        ),
      ],
    );
  }
}

class _PestanaBoton extends StatelessWidget {
  const _PestanaBoton({
    required this.titulo,
    required this.codigo,
    required this.activo,
    required this.onTap,
  });

  final String titulo;
  final String codigo;
  final bool activo;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: activo ? verde : Colors.transparent,
              width: 3.0,
            ),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              titulo,
              style: TextStyle(
                fontSize: 15,
                fontWeight: activo ? FontWeight.w900 : FontWeight.w600,
                color: activo ? verde : null,
              ),
            ),
            const SizedBox(width: 5),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
              decoration: BoxDecoration(
                color: activo
                    ? verde.withValues(alpha: 0.15)
                    : Colors.grey.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(3),
              ),
              child: Text(
                codigo,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  fontFamily: 'monospace',
                  color: activo ? verde : null,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FilaColorDetalle extends StatelessWidget {
  const _FilaColorDetalle({
    required this.rol,
    required this.color,
    required this.hex,
  });

  final String rol;
  final Color color;
  final String hex;

  @override
  Widget build(BuildContext context) {
    final esClaro = Equipo.esColorClaro(color);
    final colorTexto = esClaro ? Colors.black : Colors.white;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: esClaro ? const Color(0xFF222222) : const Color(0xFFDDDDDD),
          width: 1.8,
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            rol,
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w900,
              color: colorTexto,
            ),
          ),
          Text(
            hex.toUpperCase(),
            style: TextStyle(
              fontSize: 14,
              fontFamily: 'monospace',
              fontWeight: FontWeight.w900,
              color: colorTexto,
            ),
          ),
        ],
      ),
    );
  }
}
