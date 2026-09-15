from django import forms
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from .models import (Requerimiento, DetalleRequerimiento, OrdenCompra, DetalleOrdenCompra,
                     Material, Proyecto, Bodega, Categoria, Trabajador, HorarioTrabajador,
                     HorarioTrabajadorDia, ConfiguracionHorasExtra)

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
        fields = ['material', 'cantidad_solicitada', 'bodega_destino']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_solicitada': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
            'bodega_destino': forms.Select(attrs={'class': 'form-select', 'required': 'required'}),
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
        fields = ['categoria', 'nombre', 'descripcion', 'precio_base', 
                  'impuesto_porcentaje', 'stock_minimo', 'is_active']
        widgets = {
            'categoria': forms.Select(attrs={
                'class': 'form-select',
                'required': 'required'
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Varilla Corrugada 12mm',
                'required': 'required',
                'maxlength': '200'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Especificaciones técnicas (Opcional)'
            }),
            'precio_base': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'impuesto_porcentaje': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'value': '15'
            }),
            'stock_minimo': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Cantidad mínima para alertas'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def clean_nombre(self):
        """Validar que el nombre no sea vacío y tenga longitud mínima"""
        nombre = self.cleaned_data.get('nombre', '').strip()
        if not nombre:
            raise ValidationError("El nombre del material es obligatorio y no puede estar vacío.")
        if len(nombre) < 3:
            raise ValidationError("El nombre debe tener al menos 3 caracteres.")
        return nombre

    def clean_precio_base(self):
        """Validar que el precio no sea negativo"""
        precio = self.cleaned_data.get('precio_base')
        if precio is not None and precio < 0:
            raise ValidationError("El precio base no puede ser negativo.")
        return precio

    def clean_stock_minimo(self):
        """Validar que stock mínimo sea válido"""
        stock = self.cleaned_data.get('stock_minimo')
        if stock is not None and stock < 0:
            raise ValidationError("El stock mínimo no puede ser negativo.")
        return stock

    def clean_impuesto_porcentaje(self):
        """Validar que el porcentaje sea válido (0-100%)"""
        impuesto = self.cleaned_data.get('impuesto_porcentaje')
        if impuesto is not None:
            if impuesto < 0 or impuesto > 100:
                raise ValidationError("El porcentaje de impuesto debe estar entre 0 y 100.")
        return impuesto

class AjusteInventarioForm(forms.Form):
    bodega = forms.ModelChoiceField(
        queryset=Bodega.objects.all(), 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    cantidad_ajuste = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg fw-bold', 
            'placeholder': 'Ej: -10 para mermas, 5 para sobrantes', 
            'step': '1'
        })
    )
    observaciones = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 3, 
            'placeholder': 'Justifique el motivo de este ajuste manual...'
        }),
        required=True
    )

    def clean_cantidad_ajuste(self):
        cantidad = self.cleaned_data.get('cantidad_ajuste')
        if cantidad == 0:
            raise forms.ValidationError("El ajuste no puede ser cero.")
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
        labels = {
            'nombre': 'Nombre de la Categoría',
            'prefijo': 'Prefijo (Código Único)',
            'is_active': '¿Categoría Activa?'
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Tuberías y Conexiones PVC'}),
            'prefijo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: PVC'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


class BodegaForm(forms.ModelForm):
    class Meta:
        model = Bodega
        fields = ['nombre', 'ubicacion', 'is_principal']
        labels = {
            'is_principal': '¿Es la bodega central?'
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Bodega Norte'}),
            'ubicacion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Av. Principal y Secundaria'}),
            'is_principal': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


class TrabajadorForm(forms.ModelForm):
    email = forms.EmailField(
        required=True, error_messages={'required': 'El correo electrónico es obligatorio.'},
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'})
    )
    banco = forms.ChoiceField(
        choices=Trabajador.BANCOS, required=True,
        error_messages={'required': 'Selecciona el banco para pagos.'},
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    numero_cuenta = forms.CharField(
        required=True, max_length=20,
        error_messages={'required': 'El número de cuenta es obligatorio.'},
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número de cuenta'})
    )
    tipo_cuenta = forms.ChoiceField(
        choices=Trabajador.TIPOS_CUENTA, required=True,
        error_messages={'required': 'Selecciona el tipo de cuenta.'},
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Trabajador
        fields = ['nombres', 'apellidos', 'documento_identidad', 'cargo', 'telefono', 'email',
                  'banco', 'numero_cuenta', 'tipo_cuenta', 'periodicidad_pago', 'fecha_ingreso']
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombres'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellidos'}),
            'documento_identidad': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cédula / documento de identidad'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Soldador, Ayudante de obra'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono de contacto'}),
            'periodicidad_pago': forms.Select(attrs={'class': 'form-select'}),
            'fecha_ingreso': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def clean_numero_cuenta(self):
        numero = (self.cleaned_data.get('numero_cuenta') or '').strip()
        if not numero.isdigit():
            raise ValidationError("El número de cuenta solo puede contener dígitos.")
        if len(numero) < 6 or len(numero) > 20:
            raise ValidationError("El número de cuenta debe tener entre 6 y 20 dígitos.")
        return numero

    def clean_nombres(self):
        nombres = (self.cleaned_data.get('nombres') or '').strip()
        if len(nombres) < 2:
            raise ValidationError("El nombre debe tener al menos 2 caracteres.")
        return nombres

    def clean_apellidos(self):
        apellidos = (self.cleaned_data.get('apellidos') or '').strip()
        if len(apellidos) < 2:
            raise ValidationError("El apellido debe tener al menos 2 caracteres.")
        return apellidos

    def clean_documento_identidad(self):
        documento = (self.cleaned_data.get('documento_identidad') or '').strip()
        if not documento.isalnum():
            raise ValidationError("El documento de identidad solo puede contener letras y números.")
        if len(documento) < 5 or len(documento) > 20:
            raise ValidationError("El documento de identidad debe tener entre 5 y 20 caracteres.")
        qs = Trabajador.objects.filter(documento_identidad__iexact=documento)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Ya existe un trabajador registrado con este documento de identidad.")
        return documento


class HorarioTrabajadorDiaForm(forms.ModelForm):
    class Meta:
        model = HorarioTrabajadorDia
        fields = ['trabaja', 'hora_inicio', 'hora_fin']
        widgets = {
            'trabaja': forms.CheckboxInput(attrs={'class': 'form-check-input dia-trabaja-check'}),
            'hora_inicio': forms.TimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'time'}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('trabaja'):
            inicio, fin = cleaned.get('hora_inicio'), cleaned.get('hora_fin')
            if not inicio or not fin:
                raise ValidationError("Indica hora de inicio y fin para un día laborable.")
            if inicio >= fin:
                raise ValidationError("La hora de inicio debe ser anterior a la de fin.")
        return cleaned


HorarioDiaFormSet = forms.modelformset_factory(
    HorarioTrabajadorDia, form=HorarioTrabajadorDiaForm, extra=0
)


class ConfiguracionHorasExtraForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionHorasExtra
        fields = ['hora_inicio_ordinaria', 'hora_fin_ordinaria', 'hora_inicio_extraordinaria', 'hora_fin_extraordinaria']
        widgets = {
            'hora_inicio_ordinaria': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_fin_ordinaria': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_inicio_extraordinaria': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_fin_extraordinaria': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }

