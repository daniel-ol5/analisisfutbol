/// CU-05 · Perfil propio en móvil  —  T-025.
///
/// Muestra los datos del usuario (también sin conexión, desde la caché),
/// permite editar nombre y apellido, cambiar la contraseña y elegir el tema
/// de pantalla para uso al sol (T-023).
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
    if (mounted) context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final perfil = _perfil;
    return Scaffold(
      appBar: AppBar(title: const Text('Mi perfil')),
      body: RefreshIndicator(
        onRefresh: _cargar,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
          children: [
            if (_cargando && perfil == null)
              const Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              ),
            if (_desdeCache) ...[
              const Aviso(
                  texto: 'Sin conexión: se muestran los últimos datos guardados.'),
              const SizedBox(height: 16),
            ],
            if (_error != null) ...[
              Aviso(texto: _error!),
              const SizedBox(height: 12),
              OutlinedButton(onPressed: _cargar, child: const Text('Reintentar')),
              const SizedBox(height: 16),
            ],
            if (perfil != null) ...[
              _Datos(perfil: perfil),
              const SizedBox(height: 24),
              _Seccion(
                titulo: 'Editar mis datos',
                child: _FormularioDatos(
                  // La clave reinicia el formulario cuando llegan datos nuevos.
                  key: ValueKey('${perfil.nombre}|${perfil.apellido}'),
                  perfil: perfil,
                  alGuardar: (nuevo) => setState(() => _perfil = nuevo),
                ),
              ),
              const SizedBox(height: 24),
              const _Seccion(titulo: 'Contraseña', child: _FormularioPassword()),
            ],
            const SizedBox(height: 24),
            const _Seccion(titulo: 'Pantalla', child: _SelectorTema()),
            const SizedBox(height: 24),
            OutlinedButton.icon(
              onPressed: _salir,
              icon: const Icon(Icons.logout),
              label: const Text('Cerrar sesión'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Seccion extends StatelessWidget {
  const _Seccion({required this.titulo, required this.child});
  final String titulo;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(titulo, style: t.textTheme.titleMedium),
        const SizedBox(height: 12),
        child,
      ],
    );
  }
}

/// Criterio 1 de HU-05: nombre, apellido, email, rol y club.
class _Datos extends StatelessWidget {
  const _Datos({required this.perfil});
  final Perfil perfil;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(perfil.nombreCompleto,
                style: t.textTheme.titleLarge, key: const Key('perfil-nombre')),
            const SizedBox(height: 14),
            _Dato(etiqueta: 'Correo', valor: perfil.email),
            _Dato(etiqueta: 'Club', valor: perfil.clubNombre),
            _Dato(etiqueta: 'Rol', valor: perfil.rolLegible),
          ],
        ),
      ),
    );
  }
}

class _Dato extends StatelessWidget {
  const _Dato({required this.etiqueta, required this.valor});
  final String etiqueta;
  final String valor;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(etiqueta,
              style: t.textTheme.bodySmall?.copyWith(
                  fontWeight: FontWeight.w700,
                  color: t.colorScheme.onSurfaceVariant)),
          Text(valor, style: t.textTheme.bodyLarge),
        ],
      ),
    );
  }
}

class _FormularioDatos extends StatefulWidget {
  const _FormularioDatos({super.key, required this.perfil, required this.alGuardar});
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
          if (_error != null) ...[Aviso(texto: _error!), const SizedBox(height: 12)],
          TextFormField(
            controller: _nombre,
            decoration: const InputDecoration(labelText: 'Nombre'),
            textCapitalization: TextCapitalization.words,
            autofillHints: const [AutofillHints.givenName],
            validator: (v) => validarNombre(v, 'El nombre'),
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _apellido,
            decoration: const InputDecoration(labelText: 'Apellido'),
            textCapitalization: TextCapitalization.words,
            autofillHints: const [AutofillHints.familyName],
            validator: (v) => validarNombre(v, 'El apellido'),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _enviando ? null : _guardar,
            child: Text(_enviando ? 'Guardando…' : 'Guardar cambios'),
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
        setState(() => _error =
            e.codigo == 403 ? 'La contraseña actual es incorrecta.' : e.detalle);
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
          if (_error != null) ...[Aviso(texto: _error!), const SizedBox(height: 12)],
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
            decoration: const InputDecoration(labelText: 'Contraseña actual'),
            obscureText: true,
            autofillHints: const [AutofillHints.password],
            validator: (v) =>
                (v ?? '').isEmpty ? 'Ingresa tu contraseña actual.' : null,
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _nueva,
            decoration: const InputDecoration(
              labelText: 'Nueva contraseña',
              helperText: 'De 8 a 72 caracteres.',
            ),
            obscureText: true,
            autofillHints: const [AutofillHints.newPassword],
            validator: (v) => validarPasswordNueva(_actual.text, v),
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _confirmacion,
            decoration:
                const InputDecoration(labelText: 'Confirmar nueva contraseña'),
            obscureText: true,
            autofillHints: const [AutofillHints.newPassword],
            validator: (v) => validarConfirmacion(_nueva.text, v),
          ),
          const SizedBox(height: 16),
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
class _SelectorTema extends StatelessWidget {
  const _SelectorTema();

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<ModoTema>(
      valueListenable: modoTema,
      builder: (context, modo, _) => Wrap(
        spacing: 10,
        runSpacing: 10,
        children: [
          for (final opcion in ModoTema.values)
            ChoiceChip(
              label: Text(opcion.etiqueta),
              avatar: Icon(_icono(opcion)),
              selected: modo == opcion,
              labelStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
              materialTapTargetSize: MaterialTapTargetSize.padded,
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
              onSelected: (_) => cambiarModoTema(opcion),
            ),
        ],
      ),
    );
  }

  static IconData _icono(ModoTema modo) => switch (modo) {
        ModoTema.sistema => Icons.brightness_auto,
        ModoTema.claro => Icons.light_mode_outlined,
        ModoTema.oscuro => Icons.dark_mode_outlined,
        ModoTema.sol => Icons.wb_sunny,
      };
}
