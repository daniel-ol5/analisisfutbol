import 'package:flutter/material.dart';

import '../../shared/ui/lista_consultable.dart';
import '../deportivo/agenda/selector_partido.dart';
import 'api.dart';

class AsistenciaPagina extends StatelessWidget {
  const AsistenciaPagina({super.key});

  @override
  Widget build(BuildContext context) => DefaultTabController(
    length: 2,
    child: Scaffold(
      appBar: AppBar(
        title: const Text('Asistencia y reportes'),
        bottom: const TabBar(
          tabs: [
            Tab(text: 'Recomendaciones'),
            Tab(text: 'Reglas'),
          ],
        ),
      ),
      body: TabBarView(
        children: [
          SelectorPartido(
            contenido: (partido) => ListaConsultable<Recomendacion>(
              consultar: () => listarRecomendaciones(partido.id),
              vacio: 'Este partido aún no tiene recomendaciones activas.',
              tarjeta: (_, recomendacion) =>
                  _TarjetaRecomendacion(recomendacion),
            ),
          ),
          ListaConsultable<Regla>(
            consultar: listarReglas,
            vacio: 'Todavía no hay reglas tácticas disponibles.',
            tarjeta: (_, regla) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                leading: Icon(
                  regla.activa
                      ? Icons.check_circle_outline
                      : Icons.info_outline,
                ),
                title: Text(regla.nombre),
                subtitle: Text(regla.activa ? 'Activa' : 'Inactiva'),
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

class _TarjetaRecomendacion extends StatelessWidget {
  const _TarjetaRecomendacion(this.recomendacion);
  final Recomendacion recomendacion;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final prioridad = switch (recomendacion.prioridad) {
      'CRITICA' => 'Crítica',
      'ALTA' => 'Alta',
      'MEDIA' => 'Media',
      'BAJA' => 'Baja',
      _ => recomendacion.prioridad,
    };
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(recomendacion.mensaje, style: tema.textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(recomendacion.justificacion),
            const SizedBox(height: 8),
            Text(
              'Minuto ${recomendacion.minuto} · Prioridad $prioridad',
              style: tema.textTheme.labelLarge?.copyWith(
                color: tema.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
