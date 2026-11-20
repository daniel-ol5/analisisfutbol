import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/asistencia/push.dart';
import '../shared/ui/marca.dart';
import 'navegacion.dart';
import 'tema.dart';

class Inicio extends StatelessWidget {
  const Inicio({super.key});

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            SelloArea(),
            SizedBox(width: 10),
            Expanded(child: Text('Área Técnica', maxLines: 1, overflow: TextOverflow.ellipsis)),
          ],
        ),
        actions: [
          if (ConfigPush.disponible)
            ValueListenableBuilder<bool>(
              valueListenable: pushActivo,
              builder: (context, activo, _) => IconButton(
                tooltip: activo ? 'Notificaciones activas' : 'Activar notificaciones',
                icon: Icon(
                  activo
                      ? Icons.notifications_active_rounded
                      : Icons.notifications_none_rounded,
                ),
                onPressed: () async {
                  final mensaje = await activarPushAhora();
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context)
                    ..hideCurrentSnackBar()
                    ..showSnackBar(SnackBar(content: Text(mensaje)));
                },
              ),
            ),
          // Asistente de uso con IA.
          IconButton(
            key: const Key('abrir-asistente'),
            tooltip: 'Asistente',
            icon: const Icon(Icons.support_agent_rounded),
            onPressed: () => context.push('/asistente?pantalla=inicio'),
          ),
          IconButton(
            tooltip: 'Mi perfil',
            icon: const Icon(Icons.person_outline),
            onPressed: () => context.go('/perfil'),
          ),
        ],
      ),
      body: SafeArea(
        top: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 20, 16, 28),
          children: [
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 960),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text('Panel del club', style: tema.textTheme.headlineSmall),
                    const SizedBox(height: 14),
                    const _DiaDePartido(),
                    const SizedBox(height: 22),
                    Text('Módulos', style: tema.textTheme.titleMedium),
                    const SizedBox(height: 10),
                    LayoutBuilder(
                      builder: (context, limites) {
                        const espacio = 10.0;
                        final escala =
                            MediaQuery.textScalerOf(context).scale(16) / 16;
                        final columnas = (limites.maxWidth / (141 * escala))
                            .floor()
                            .clamp(1, 3);
                        final ancho =
                            (limites.maxWidth - (columnas - 1) * espacio) /
                            columnas;
                        return Wrap(
                          spacing: espacio,
                          runSpacing: espacio,
                          children: [
                            for (final modulo in modulos)
                              SizedBox(
                                width: ancho,
                                child: _TarjetaModulo(modulo),
                              ),
                          ],
                        );
                      },
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DiaDePartido extends StatelessWidget {
  const _DiaDePartido();

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: const BoxDecoration(
      borderRadius: BorderRadius.all(Radius.circular(16)),
      gradient: LinearGradient(colors: [canchaOscura, canchaClara]),
    ),
    child: ClipRRect(
      borderRadius: const BorderRadius.all(Radius.circular(16)),
      child: Stack(
        children: [
          const Positioned.fill(child: CustomPaint(painter: _DibujoCancha())),
          Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Día de partido',
                  style: Theme.of(
                    context,
                  ).textTheme.titleLarge?.copyWith(color: Colors.white),
                ),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: () => context.go('/partidos'),
                  style: FilledButton.styleFrom(
                    backgroundColor: limaMarca,
                    foregroundColor: menuOscuro,
                  ),
                  icon: const Icon(Icons.arrow_forward_rounded, size: 20),
                  label: const Text('Abrir agenda'),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

class _DibujoCancha extends CustomPainter {
  const _DibujoCancha();

  @override
  void paint(Canvas canvas, Size size) {
    final ancho = size.width * .43;
    final campo = Rect.fromLTWH(
      size.width - ancho * .8,
      13,
      ancho,
      size.height - 26,
    );
    final linea = Paint()
      ..color = limaMarca.withValues(alpha: .25)
      ..strokeWidth = 1
      ..style = PaintingStyle.stroke;
    canvas.save();
    canvas.translate(campo.center.dx, campo.center.dy);
    canvas.rotate(-.17);
    canvas.translate(-campo.center.dx, -campo.center.dy);
    canvas.drawRect(campo, linea);
    canvas.drawLine(campo.topCenter, campo.bottomCenter, linea);
    canvas.drawCircle(campo.center, campo.shortestSide * .17, linea);
    canvas.drawRect(
      Rect.fromLTWH(
        campo.left,
        campo.top + campo.height * .26,
        ancho * .18,
        campo.height * .48,
      ),
      linea,
    );
    canvas.restore();
  }

  @override
  bool shouldRepaint(_DibujoCancha oldDelegate) => false;
}

class _TarjetaModulo extends StatelessWidget {
  const _TarjetaModulo(this.modulo);
  final Modulo modulo;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final esquema = tema.colorScheme;
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.go(modulo.ruta),
        child: Container(
          constraints: const BoxConstraints(minHeight: 113),
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: esquema.secondaryContainer,
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Icon(
                  modulo.icono,
                  color: esquema.onSecondaryContainer,
                  size: 22,
                ),
              ),
              const SizedBox(height: 9),
              Text(modulo.nombre, style: tema.textTheme.labelLarge),
            ],
          ),
        ),
      ),
    );
  }
}
