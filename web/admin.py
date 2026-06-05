from django.contrib import admin
from .models import (
    Proyecto, Material, Requerimiento, DetalleRequerimiento, 
    MovimientoInventario, OrdenCompra, DetalleOrdenCompra
)
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import PerfilEmpleado

# =====================================================================
# 1. PROYECTOS
# =====================================================================
@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('centro_costos', 'nombre', 'is_active', 'fecha_creacion')
    list_filter = ('is_active',)
    search_fields = ('nombre', 'centro_costos')

# =====================================================================
# 2. INVENTARIO (Materiales y Consumibles)
# =====================================================================
@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    # 'tipo' ya no existe, usamos 'categoria'
    list_display = ('sku', 'nombre', 'categoria', 'stock_actual') 
    list_filter = ('categoria',) # Filtramos por la relación de Categoria
    search_fields = ('nombre', 'sku')

# =====================================================================
# 3. REQUERIMIENTOS (Tickets Internos)
# =====================================================================
class DetalleRequerimientoInline(admin.TabularInline):
    model = DetalleRequerimiento
    extra = 0

@admin.register(Requerimiento)
class RequerimientoAdmin(admin.ModelAdmin):
    list_display = ('folio', 'solicitante', 'proyecto', 'fecha_solicitud', 'estado')
    list_filter = ('estado', 'proyecto', 'fecha_solicitud')
    search_fields = ('folio', 'solicitante__username', 'proyecto__nombre')
    inlines = [DetalleRequerimientoInline]
    # Hacemos que el folio sea de solo lectura para evitar que alguien lo altere
    readonly_fields = ('folio',) 

# =====================================================================
# 4. AUDITORÍA (Movimientos de Inventario)
# =====================================================================
@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('material', 'tipo', 'cantidad', 'fecha_hora', 'responsable')
    list_filter = ('tipo', 'fecha_hora')
    search_fields = ('material__nombre', 'responsable__username')
    # Estos campos son de auditoría, no deberían poder editarse a mano
    readonly_fields = ('fecha_hora',) 

# =====================================================================
# 5. ÓRDENES DE COMPRA (Abastecimiento)
# =====================================================================
class DetalleOrdenCompraInline(admin.TabularInline):
    model = DetalleOrdenCompra
    extra = 0

@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = ('folio', 'proveedor', 'creado_por', 'fecha_creacion', 'estado')
    list_filter = ('estado', 'fecha_creacion')
    search_fields = ('folio', 'proveedor', 'creado_por__username')
    inlines = [DetalleOrdenCompraInline]
    readonly_fields = ('folio',)

class PerfilEmpleadoInline(admin.StackedInline):
    model = PerfilEmpleado
    can_delete = False
    verbose_name_plural = 'Asignación de Bodega (Solo para Bodegueros)'
    fk_name = 'usuario'

class CustomUserAdmin(UserAdmin):
    inlines = (PerfilEmpleadoInline, )

# Re-registramos el modelo User con nuestra nueva configuración
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)