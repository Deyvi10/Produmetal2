from django import forms
from django.contrib.auth.models import User, Group
from .models import (Requerimiento, DetalleRequerimiento, OrdenCompra, DetalleOrdenCompra, 
                     Material, Proyecto, Bodega)

class RequerimientoForm(forms.ModelForm):
    class Meta:
        model = Requerimiento
        fields = ['proyecto', 'observaciones']
        widgets = {
            'proyecto': forms.Select(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class DetalleRequerimientoForm(forms.ModelForm):
    class Meta:
        model = DetalleRequerimiento
        fields = ['material', 'cantidad_solicitada']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-control'}),
            'cantidad_solicitada': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.1', 'step': '0.01'}),
        }

class RegistroEmpleadoForm(forms.ModelForm):
    rol = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        empty_label="Seleccione un cargo...",
        widget=forms.Select(attrs={'class': 'form-select', 'required': 'required'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'password': forms.PasswordInput(attrs={'class': 'form-control'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            user.groups.add(self.cleaned_data['rol'])
        return user
    
class OrdenCompraForm(forms.ModelForm):
    class Meta:
        model = OrdenCompra
        fields = ['proveedor', 'numero_factura', 'observaciones', 'documento_respaldo']
        widgets = {
            'proveedor': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_factura': forms.TextInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'documento_respaldo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

class DetalleOrdenCompraForm(forms.ModelForm):
    class Meta:
        model = DetalleOrdenCompra
        fields = ['material', 'cantidad_pedida']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-select fw-bold'}),
            'cantidad_pedida': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }

class ProyectoForm(forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = ['nombre', 'centro_costos', 'descripcion', 'is_active'] # AÑADIDO: descripcion
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'centro_costos': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional (Auto)'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        # Eliminamos 'sku' para que sea automático
        fields = ['nombre', 'tipo', 'subcategoria', 'descripcion', 'stock_minimo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'subcategoria': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }

class AjusteInventarioForm(forms.Form):
    bodega = forms.ModelChoiceField(queryset=Bodega.objects.all(), widget=forms.Select(attrs={'class': 'form-select'}))
    cantidad_ajuste = forms.DecimalField(
        max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-lg fw-bold', 'placeholder': 'Ej: -10'})
    )
    observaciones = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), required=True
    )

class VentaMaterialForm(forms.Form):
    material = forms.ModelChoiceField(queryset=Material.objects.filter(is_active=True), widget=forms.Select(attrs={'class': 'form-select'}))
    bodega_origen = forms.ModelChoiceField(queryset=Bodega.objects.all(), widget=forms.Select(attrs={'class': 'form-select'}))
    cantidad = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    comprador = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
    factura = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

class RecepcionMaterialForm(forms.Form):
    bodega_destino = forms.ModelChoiceField(
        queryset=Bodega.objects.all(), 
        empty_label="Seleccione bodega para ingresar stock...",
        widget=forms.Select(attrs={'class': 'form-select mb-3', 'required': 'required'})
    )
    def __init__(self, *args, **kwargs):
        detalles = kwargs.pop('detalles', [])
        super().__init__(*args, **kwargs)
        for item in detalles:
            self.fields[f'recibido_{item.id}'] = forms.DecimalField(
                initial=item.cantidad_pedida, max_value=item.cantidad_pedida,
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )
            self.fields[f'certificado_{item.id}'] = forms.FileField(
                required=False, 
                widget=forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm', 'accept': 'application/pdf'})
            )