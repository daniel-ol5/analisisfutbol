/// CU-05 · Perfil propio en móvil  —  T-025.
///
/// Muestra los datos del usuario (también sin conexión, desde la caché),
/// permite editar nombre y apellido, cambiar la contraseña y elegir el tema
/// de pantalla para uso al sol (T-023) dentro de tarjetas bien estructuradas.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/tema.dart';
import '../../shared/api/cliente.dart';
import 'api.dart';
import 'modelos.dart';
import 'validacion.dart';
import 'widgets/aviso.dart';

class PerfilPagina extends StatefulWidget {
  const PerfilPagina({super.key});

  @override
  State<PerfilPagina> createState() => _PerfilPaginaState();
}

class _PerfilPaginaState extends State<PerfilPagina> {
  Perfil? _perfil;
  bool _cargando = true;
  String? _error;

  /// true si lo que se muestra viene de la caché porque la red falló.
  bool _desdeCache = false;

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  Future<void> _cargar() async {
    // Primero la caché: el perfil aparece al instante, aun sin señal.
    final enCache = await perfilEnCache();
    if (mounted && enCache != null && _perfil == null) {
      setState(() => _perfil = enCache);
    }
    try {
      final perfil = await obtenerPerfil();
      if (!mounted) return;
      setState(() {
        _perfil = perfil;
        _error = null;
        _desdeCache = false;
      });
    } on ErrorApi catch (e) {
      if (mounted) setState(() => _error = e.detalle);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _desdeCache = _perfil != null;
        _error = _perfil == null ? 'Sin conexión con el servidor.' : null;
      });
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  Future<void> _salir() async {
    await cerrarSesion();
    if (mounted) context.go('/seguridad');
  }

  @override
  Widget build(BuildContext context) {
    final perfil = _perfil;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mi perfil'),
        actions: [
          IconButton(
            onPressed: _cargando ? null : _cargar,
            tooltip: 'Sincronizar perfil',
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _cargar,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 680),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 36),
              children: [
                if (_cargando && perfil == null)
                  const Padding(
                    padding: EdgeInsets.all(32),
                    child: Center(child: CircularProgressIndicator()),
                  ),
                if (_desdeCache) ...[
                  const Aviso(
                    texto:
                        'Sin conexión: se muestran los últimos datos guardados.',
                  ),
                  const SizedBox(height: 12),
                ],
                if (_error != null) ...[
                  Aviso(texto: _error!),
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    onPressed: _cargar,
                    icon: const Icon(Icons.refresh_rounded),
                    label: const Text('Reintentar'),
                  ),
                  const SizedBox(height: 14),
                ],
                if (perfil != null) ...[
                  _Datos(perfil: perfil),
                  const SizedBox(height: 14),
                ],
                const _Seccion(
                  icono: Icons.contrast_rounded,
                  titulo: 'Pantalla',
                  subtitulo:
                      'Ajusta el contraste según la iluminación del campo (T-023).',
                  child: _SelectorTema(),
                ),
                if (perfil != null) ...[
                  const SizedBox(height: 14),
                  _Seccion(
                    icono: Icons.badge_outlined,
                    titulo: 'Editar mis datos',
                    subtitulo:
                        'Nombre visible en reportes, bitácoras y alineaciones.',
                    child: _FormularioDatos(
                      // La clave reinicia el formulario cuando llegan datos nuevos.
                      key: ValueKey('${perfil.nombre}|${perfil.apellido}'),
                      perfil: perfil,
                      alGuardar: (nuevo) => setState(() => _perfil = nuevo),
                    ),
                  ),
                  const SizedBox(height: 14),
                  const _Seccion(
                    icono: Icons.lock_outline_rounded,
                    titulo: 'Contraseña',
                    subtitulo:
                        'Al actualizarla se cerrarán tus sesiones en otros dispositivos.',
                    child: _FormularioPassword(),
                  ),
                ],
                const SizedBox(height: 18),
                _TarjetaCerrarSesion(alSalir: _salir),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Seccion extends StatelessWidget {
  const _Seccion({
    required this.icono,
    required this.titulo,
    required this.subtitulo,
    required this.child,
  });

  final IconData icono;
  final String titulo;
  final String subtitulo;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final cs = t.colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: cs.secondaryContainer,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(
                    icono,
                    color: cs.primary,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(titulo, style: t.textTheme.titleMedium),
                      Text(
                        subtitulo,
                        style: t.textTheme.bodySmall?.copyWith(
                          fontSize: 16,
                          color: cs.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Divider(height: 1, color: cs.outlineVariant),
            const SizedBox(height: 14),
            child,
          ],
        ),
      ),
    );
  }
}

/// Criterio 1 de HU-05: nombre, apellido, email, rol y club.
class _Datos extends StatelessWidget {
  const _Datos({required this.perfil});
  final Perfil perfil;

  String get _iniciales {
    final n = perfil.nombre.trim();
    final a = perfil.apellido.trim();
    final i1 = n.isNotEmpty ? n[0] : '';
    final i2 = a.isNotEmpty ? a[0] : '';
    final res = '$i1$i2'.toUpperCase();
    return res.isEmpty ? 'AT' : res;
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final cs = t.colorScheme;

    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Franja superior con avatar, nombre y rol
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              color: cs.secondaryContainer.withValues(alpha: 0.55),
              border: Border(
                bottom: BorderSide(color: cs.outlineVariant, width: 1),
              ),
            ),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [verde, verdeClaro],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    _iniciales,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 0.5,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        perfil.nombreCompleto,
                        style: t.textTheme.titleLarge,
                        key: const Key('perfil-nombre'),
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Icon(
                            Icons.verified_user_outlined,
                            size: 16,
                            color: cs.primary,
                          ),
                          const SizedBox(width: 5),
                          Flexible(
                            child: Text(
                              perfil.rolLegible,
                              style: t.textTheme.bodySmall?.copyWith(
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                                color: cs.onSurface,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // Metadatos del usuario (Correo y Club)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: LayoutBuilder(
              builder: (context, constraints) {
                if (constraints.maxWidth >= 420) {
                  return Row(
                    children: [
                      Expanded(
                        child: _Dato(
                          icono: Icons.mail_outline_rounded,
                          etiqueta: 'Correo',
                          valor: perfil.email,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _Dato(
                          icono: Icons.shield_outlined,
                          etiqueta: 'Club',
                          valor: perfil.clubNombre,
                        ),
                      ),
                    ],
                  );
                }
                return Column(
                  children: [
                    _Dato(
                      icono: Icons.mail_outline_rounded,
                      etiqueta: 'Correo',
                      valor: perfil.email,
                    ),
                    Divider(height: 14, color: cs.outlineVariant),
                    _Dato(
                      icono: Icons.shield_outlined,
                      etiqueta: 'Club',
                      valor: perfil.clubNombre,
                    ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _Dato extends StatelessWidget {
  const _Dato({
    required this.icono,
    required this.etiqueta,
    required this.valor,
  });

  final IconData icono;
  final String etiqueta;
  final String valor;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final cs = t.colorScheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Icon(icono, size: 19, color: cs.onSurfaceVariant),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                etiqueta,
                style: t.textTheme.bodySmall?.copyWith(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: cs.onSurfaceVariant,
                ),
              ),
              Text(
                valor,
                style: t.textTheme.bodyLarge?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _FormularioDatos extends StatefulWidget {
  const _FormularioDatos({
    super.key,
    required this.perfil,
    required this.alGuardar,
  });

  final Perfil perfil;
  final ValueChanged<Perfil> alGuardar;

  @override
  State<_FormularioDatos> createState() => _FormularioDatosState();
}

class _FormularioDatosState extends State<_FormularioDatos> {
  final _formulario = GlobalKey<FormState>();
  late final _nombre = TextEditingController(text: widget.perfil.nombre);
  late final _apellido = TextEditingController(text: widget.perfil.apellido);
  bool _enviando = false;
  String? _error;

  @override
  void dispose() {
    _nombre.dispose();
    _apellido.dispose();
    super.dispose();
  }

  Future<void> _guardar() async {
    if (!_formulario.currentState!.validate()) return;
    setState(() {
      _enviando = true;
      _error = null;
    });
    try {
      final nuevo = await editarPerfil(
        nombre: _nombre.text.trim(),
        apellido: _apellido.text.trim(),
      );
      widget.alGuardar(nuevo);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Datos actualizados.')));
      }
    } on ErrorApi catch (e) {
      if (mounted) setState(() => _error = e.detalle);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Sin conexión: no se guardaron los cambios.');
      }
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formulario,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_error != null) ...[
            Aviso(texto: _error!),
            const SizedBox(height: 12),
          ],
          TextFormField(
            controller: _nombre,
            decoration: const InputDecoration(
              labelText: 'Nombre',
              prefixIcon: Icon(Icons.person_outline_rounded),
            ),
            textCapitalization: TextCapitalization.words,
            autofillHints: const [AutofillHints.givenName],
            validator: (v) => validarNombre(v, 'El nombre'),
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _apellido,
            decoration: const InputDecoration(
              labelText: 'Apellido',
              prefixIcon: Icon(Icons.badge_outlined),
            ),
            textCapitalization: TextCapitalization.words,
            autofillHints: const [AutofillHints.familyName],
            validator: (v) => validarNombre(v, 'El apellido'),
          ),
          const SizedBox(height: 14),
          FilledButton.icon(
            onPressed: _enviando ? null : _guardar,
            icon: const Icon(Icons.check_rounded, size: 20),
            label: Text(_enviando ? 'Guardando…' : 'Guardar cambios'),
          ),
        ],
      ),
    );
  }
}

class _FormularioPassword extends StatefulWidget {
  const _FormularioPassword();

  @override
  State<_FormularioPassword> createState() => _FormularioPasswordState();
}

class _FormularioPasswordState extends State<_FormularioPassword> {
  final _formulario = GlobalKey<FormState>();
  final _actual = TextEditingController();
  final _nueva = TextEditingController();
  final _confirmacion = TextEditingController();
  bool _enviando = false;
  String? _error;
  bool _cambiada = false;

  bool _ocultarActual = true;
  bool _ocultarNueva = true;
  bool _ocultarConfirmacion = true;

  @override
  void dispose() {
    _actual.dispose();
    _nueva.dispose();
    _confirmacion.dispose();
    super.dispose();
  }

  Future<void> _cambiar() async {
    if (!_formulario.currentState!.validate()) return;
    setState(() {
      _enviando = true;
      _error = null;
      _cambiada = false;
    });
    try {
      await cambiarPassword(actual: _actual.text, nueva: _nueva.text);
      _actual.clear();
      _nueva.clear();
      _confirmacion.clear();
      if (mounted) setState(() => _cambiada = true);
    } on ErrorApi catch (e) {
      if (mounted) {
        setState(() => _error = e.codigo == 403
            ? 'La contraseña actual es incorrecta.'
            : e.detalle);
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Sin conexión: la contraseña no se cambió.');
      }
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formulario,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_error != null) ...[
            Aviso(texto: _error!),
            const SizedBox(height: 12),
          ],
          if (_cambiada) ...[
            const Aviso(
              exito: true,
              texto: 'Contraseña cambiada. Se cerraron tus demás sesiones; '
                  'esta sigue activa.',
            ),
            const SizedBox(height: 12),
          ],
          TextFormField(
            controller: _actual,
            decoration: InputDecoration(
              labelText: 'Contraseña actual',
              prefixIcon: const Icon(Icons.lock_outline_rounded),
              suffixIcon: IconButton(
                onPressed: () =>
                    setState(() => _ocultarActual = !_ocultarActual),
                icon: Icon(
                  _ocultarActual
                      ? Icons.visibility_outlined
                      : Icons.visibility_off_outlined,
                ),
              ),
            ),
            obscureText: _ocultarActual,
            autofillHints: const [AutofillHints.password],
            validator: (v) =>
                (v ?? '').isEmpty ? 'Ingresa tu contraseña actual.' : null,
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _nueva,
            decoration: InputDecoration(
              labelText: 'Nueva contraseña',
              helperText: 'De 8 a 72 caracteres.',
              prefixIcon: const Icon(Icons.key_rounded),
              suffixIcon: IconButton(
                onPressed: () =>
                    setState(() => _ocultarNueva = !_ocultarNueva),
                icon: Icon(
                  _ocultarNueva
                      ? Icons.visibility_outlined
                      : Icons.visibility_off_outlined,
                ),
              ),
            ),
            obscureText: _ocultarNueva,
            autofillHints: const [AutofillHints.newPassword],
            validator: (v) => validarPasswordNueva(_actual.text, v),
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _confirmacion,
            decoration: InputDecoration(
              labelText: 'Confirmar nueva contraseña',
              prefixIcon: const Icon(Icons.verified_outlined),
              suffixIcon: IconButton(
                onPressed: () => setState(
                  () => _ocultarConfirmacion = !_ocultarConfirmacion,
                ),
                icon: Icon(
                  _ocultarConfirmacion
                      ? Icons.visibility_outlined
                      : Icons.visibility_off_outlined,
                ),
              ),
            ),
            obscureText: _ocultarConfirmacion,
            autofillHints: const [AutofillHints.newPassword],
            validator: (v) => validarConfirmacion(_nueva.text, v),
          ),
          const SizedBox(height: 18),
          FilledButton(
            onPressed: _enviando ? null : _cambiar,
            child: Text(_enviando ? 'Cambiando…' : 'Cambiar contraseña'),
          ),
        ],
      ),
    );
  }
}

/// T-023: el modo sol se activa con un toque y queda guardado (T-024).
/// En móviles se organiza en una cuadrícula uniforme de 2×2 y en pantallas
/// anchas en 4 columnas iguales.
class _SelectorTema extends StatelessWidget {
  const _SelectorTema();

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    const opciones = ModoTema.values;

    return ValueListenableBuilder<ModoTema>(
      valueListenable: modoTema,
      builder: (context, modo, _) => LayoutBuilder(
        builder: (context, constraints) {
          const separacion = 10.0;
          final columnas = constraints.maxWidth >= 520 ? 4 : 2;
          final anchoColumna =
              (constraints.maxWidth - separacion * (columnas - 1)) / columnas;

          return Wrap(
            spacing: separacion,
            runSpacing: separacion,
            children: [
              for (final opcion in opciones)
                SizedBox(
                  width: anchoColumna,
                  child: ChoiceChip(
                    showCheckmark: false,
                    avatar: Icon(
                      _icono(opcion),
                      size: 20,
                      color: modo == opcion ? cs.primary : cs.onSurfaceVariant,
                    ),
                    label: SizedBox(
                      width: double.infinity,
                      child: Text(
                        opcion.etiqueta,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    selected: modo == opcion,
                    selectedColor: cs.secondaryContainer,
                    backgroundColor: cs.surface,
                    side: BorderSide(
                      color: modo == opcion ? cs.primary : cs.outlineVariant,
                      width: modo == opcion ? 1.8 : 1,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                    labelStyle: TextStyle(
                      fontSize: 16,
                      fontWeight:
                          modo == opcion ? FontWeight.w800 : FontWeight.w600,
                      color: cs.onSurface,
                    ),
                    materialTapTargetSize: MaterialTapTargetSize.padded,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 12,
                    ),
                    onSelected: (_) => cambiarModoTema(opcion),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  static IconData _icono(ModoTema modo) => switch (modo) {
        ModoTema.sistema => Icons.brightness_auto_rounded,
        ModoTema.claro => Icons.light_mode_outlined,
        ModoTema.oscuro => Icons.dark_mode_outlined,
        ModoTema.sol => Icons.wb_sunny_rounded,
      };
}

class _TarjetaCerrarSesion extends StatelessWidget {
  const _TarjetaCerrarSesion({required this.alSalir});
  final VoidCallback alSalir;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return OutlinedButton.icon(
      onPressed: alSalir,
      style: OutlinedButton.styleFrom(
        foregroundColor: cs.error,
        side: BorderSide(color: cs.error.withValues(alpha: 0.6), width: 1.5),
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 18),
      ),
      icon: const Icon(Icons.logout_rounded),
      label: const Text('Cerrar sesión'),
    );
  }
}
