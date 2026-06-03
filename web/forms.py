from django import forms
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from .models import (Requerimiento, DetalleRequerimiento, OrdenCompra, DetalleOrdenCompra, 
                     Material, Proyecto, Bodega, Categoria)

# =======================================================
# HELPERS Y VALIDACIONES GLOBALES
# =======================================================
def validar_tamano_archivo(file):
    max_size_mb = 5
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"El archivo es demasiado grande. El tamaño máximo es {max_size_mb}MB.")
    return file

# =======================================================
# FORMULARIOS DEL SISTEMA
# =======================================================

class RequerimientoForm(forms.ModelForm):
    class Meta:
        model = Requerimiento
        fields = ['proyecto', 'observaciones']
        widgets = {
            'proyecto': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Justifique brevemente el requerimiento...'}),
        }

class DetalleRequerimientoForm(forms.ModelForm):
    class Meta:
        model = DetalleRequerimiento
        fields = ['material', 'cantidad_solicitada']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_solicitada': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
        }
        
    def clean_cantidad_solicitada(self):
        cantidad = self.cleaned_data.get('cantidad_solicitada')
        if cantidad is None or cantidad <= 0:
            raise ValidationError("La cantidad solicitada debe ser estrictamente mayor a 0.")
        return cantidad

class RegistroEmpleadoForm(forms.ModelForm):
    rol = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        empty_label="Seleccione un departamento/rol...",
        widget=forms.Select(attrs={'class': 'form-select', 'required': 'required'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'password': forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        }

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if len(password) < 8:
            raise ValidationError("Por políticas de seguridad, la contraseña debe tener al menos 8 caracteres.")
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"]) # Encriptación obligatoria
        if commit:
            user.save()
            user.groups.add(self.cleaned_data['rol'])
        return user
    
class OrdenCompraForm(forms.ModelForm):
    class Meta:
        model = OrdenCompra
        fields = ['proveedor', 'numero_factura', 'observaciones', 'documento_respaldo']
        widgets = {
            'proveedor': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Razón social del proveedor'}),
            'numero_factura': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'N° Factura (Opcional)'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'documento_respaldo': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}),
        }

    def clean_documento_respaldo(self):
        file = self.cleaned_data.get('documento_respaldo', False)
        if file:
            return validar_tamano_archivo(file)
        return file

class DetalleOrdenCompraForm(forms.ModelForm):
    class Meta:
        model = DetalleOrdenCompra
        fields = ['material', 'cantidad_pedida']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-select fw-bold'}),
            'cantidad_pedida': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
        }
        
    def clean_cantidad_pedida(self):
        cantidad = self.cleaned_data.get('cantidad_pedida')
        if cantidad is None or cantidad <= 0:
            raise ValidationError("La cantidad a comprar debe ser mayor a 0.")
        return cantidad

class ProyectoForm(forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = ['nombre', 'centro_costos', 'descripcion', 'is_active']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la obra o cliente'}),
            'centro_costos': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional (Dejar en blanco para autogenerar)'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        # CORRECCIÓN CRÍTICA: Adaptado a la nueva arquitectura de Categoria (se eliminó tipo y subcategoria)
        fields = ['categoria', 'nombre', 'descripcion', 'stock_minimo']
        widgets = {
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Varilla Corrugada 12mm'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
        }

class AjusteInventarioForm(forms.Form):
    bodega = forms.ModelChoiceField(
        queryset=Bodega.objects.all(), 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    cantidad_ajuste = forms.DecimalField(
        max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-lg fw-bold', 'placeholder': 'Ej: -10 para mermas, 5 para sobrantes'})
    )
    observaciones = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Justifique obligatoriamente el motivo del ajuste (Pérdida, conteo, rotura...)'}), 
        required=True
    )
    
    def clean_cantidad_ajuste(self):
        cantidad = self.cleaned_data.get('cantidad_ajuste')
        if cantidad == 0:
            raise ValidationError("El ajuste no puede ser cero.")
        return cantidad

class VentaMaterialForm(forms.Form):
    material = forms.ModelChoiceField(
        queryset=Material.objects.filter(is_active=True), 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    bodega_origen = forms.ModelChoiceField(
        queryset=Bodega.objects.all(), 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    cantidad = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=0.01, 
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    comprador = forms.CharField(
        max_length=200, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del cliente externo'})
    )
    factura = forms.CharField(
        max_length=50, required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'N° de Factura / Ticket (Opcional)'})
    )

class RecepcionMaterialForm(forms.Form):
    bodega_destino = forms.ModelChoiceField(
        queryset=Bodega.objects.all(), 
        empty_label="Seleccione la bodega física que recibe...",
        widget=forms.Select(attrs={'class': 'form-select mb-3', 'required': 'required'})
    )
    
    def __init__(self, *args, **kwargs):
        detalles = kwargs.pop('detalles', [])
        super().__init__(*args, **kwargs)
        for item in detalles:
            # Control estricto: El bodeguero no puede registrar más de lo que se pidió
            self.fields[f'recibido_{item.id}'] = forms.DecimalField(
                initial=item.cantidad_pedida, max_value=item.cantidad_pedida, min_value=0,
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )
            # Solo permitimos PDFs para los certificados en bodega
            self.fields[f'certificado_{item.id}'] = forms.FileField(
                required=False, 
                widget=forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm', 'accept': 'application/pdf'})
            )
class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'prefijo', 'is_active']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Ferretería'}),
            'prefijo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: FER'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class BodegaForm(forms.ModelForm):
    class Meta:
        model = Bodega
        fields = ['nombre', 'ubicacion', 'is_principal']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'ubicacion': forms.TextInput(attrs={'class': 'form-control'}),
            'is_principal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }