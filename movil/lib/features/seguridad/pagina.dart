/// Seguridad y Administración  —  P1
///
/// CU-02 Iniciar sesión / CU-03 Cerrar sesión.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/tema.dart';
import '../../shared/api/almacenamiento.dart';
import '../../shared/api/cliente.dart';
import 'api.dart' as seguridad_api;
import 'validacion.dart';

class SeguridadPagina extends StatefulWidget {
  const SeguridadPagina({super.key});

  @override
  State<SeguridadPagina> createState() => _SeguridadPaginaState();
}

class _SeguridadPaginaState extends State<SeguridadPagina> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();

  bool _verificandoSesion = true;
  bool _cargando = false;
  bool _ocultarPassword = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _verificarSesion();
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _verificarSesion() async {
    try {
      final activa = await Almacenamiento.haySesion();
      if (!mounted) return;
      if (activa) {
        context.go('/');
        return;
      }
    } catch (_) {}
    if (mounted) {
      setState(() => _verificandoSesion = false);
    }
  }

  Future<void> _iniciarSesion() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      await seguridad_api.iniciarSesion(
        _email.text.trim().toLowerCase(),
        _password.text,
      );
      if (!mounted) return;
      context.go('/');
    } on ErrorApi catch (e) {
      if (!mounted) return;
      setState(() {
        _error = switch (e.codigo) {
          401 => 'Correo o contraseña incorrectos.',
          403 => 'La cuenta está desactivada.',
          422 => 'Ingresa un correo electrónico con formato válido.',
          501 => 'Caso de uso aún no disponible: ${e.detalle}',
          _ => e.detalle,
        };
      });
    } on TimeoutException {
      if (!mounted) return;
      setState(() {
        _error =
            'Tiempo de espera agotado. Verifica que el backend esté activo en el puerto 8000.';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error =
            'No se pudo conectar con el servidor. Verifica que el backend esté activo.';
      });
    } finally {
      if (mounted) {
        setState(() => _cargando = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: _verificandoSesion
            ? const Center(child: CircularProgressIndicator())
            : Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 440),
                  child: _vistaLogin(t),
                ),
              ),
      ),
    );
  }

  Widget _cabecera(
    ThemeData t,
    String etiqueta,
    List<TextSpan> titulo,
    String subtitulo,
  ) =>
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [verde, verdeClaro],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(
                  Icons.sports_soccer,
                  color: Colors.white,
                  size: 20,
                ),
              ),
              const SizedBox(width: 10),
              Text(
                etiqueta,
                style: t.textTheme.bodySmall?.copyWith(
                  fontSize: 11,
                  letterSpacing: 1.2,
                  fontWeight: FontWeight.w800,
                  color: verde,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text.rich(
            TextSpan(children: titulo),
            style: t.textTheme.titleLarge?.copyWith(
              fontSize: 30,
              fontWeight: FontWeight.w900,
              letterSpacing: -0.4,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            subtitulo,
            style: t.textTheme.bodyMedium?.copyWith(
              color: t.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      );

  Widget _vistaLogin(ThemeData t) => Form(
        key: _formKey,
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
          children: [
            _cabecera(
              t,
              'ÁREA TÉCNICA · ACCESO',
              [
                const TextSpan(text: 'Iniciar '),
                const TextSpan(text: 'sesión', style: TextStyle(color: verde)),
              ],
              'Ingresa con tu correo y contraseña del club para continuar.',
            ),
            const SizedBox(height: 22),
            Card(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(18, 20, 18, 22),
                child: Column(
                  children: [
                    TextFormField(
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.next,
                      decoration: const InputDecoration(
                        labelText: 'Correo electrónico',
                        prefixIcon: Icon(Icons.person_outline),
                      ),
                      validator: validarEmail,
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _password,
                      obscureText: _ocultarPassword,
                      textInputAction: TextInputAction.done,
                      onFieldSubmitted: (_) =>
                          _cargando ? null : _iniciarSesion(),
                      decoration: InputDecoration(
                        labelText: 'Contraseña',
                        prefixIcon: const Icon(Icons.lock_outline),
                        suffixIcon: IconButton(
                          icon: Icon(
                            _ocultarPassword
                                ? Icons.visibility_outlined
                                : Icons.visibility_off_outlined,
                          ),
                          onPressed: () => setState(
                            () => _ocultarPassword = !_ocultarPassword,
                          ),
                        ),
                      ),
                      validator: validarRequerida,
                    ),
                  ],
                ),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 16),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                decoration: BoxDecoration(
                  color: rojo.withValues(alpha: 0.08),
                  border: Border.all(color: rojo),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.error_outline, color: rojo, size: 20),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        _error!,
                        style: const TextStyle(
                          color: rojo,
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 22),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _cargando ? null : _iniciarSesion,
                child: _cargando
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          color: Colors.white,
                        ),
                      )
                    : const Text('Iniciar sesión'),
              ),
            ),
          ],
        ),
      );
}
