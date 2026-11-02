from PIL import Image, UnidentifiedImageError
from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            return [super().clean(item, initial) for item in data]
        return super().clean(data, initial)


class UserSignupForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'password1', 'password2')


class MultiImageUploadForm(forms.Form):
    MAX_FILE_SIZE = 10 * 1024 * 1024

    images = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={
            'multiple': True,
            'accept': 'image/*',
        }),
    )

    def clean(self):
        cleaned_data = super().clean()
        files = self.files.getlist('images')
        if not files:
            raise forms.ValidationError('Select at least one image.')

        for uploaded_file in files:
            if uploaded_file.size > self.MAX_FILE_SIZE:
                raise forms.ValidationError(
                    f'{uploaded_file.name} exceeds the 10 MB file size limit.'
                )
            try:
                with Image.open(uploaded_file) as image:
                    image.verify()
            except (UnidentifiedImageError, OSError):
                raise forms.ValidationError(
                    f'{uploaded_file.name} is not a valid image file.'
                )
            uploaded_file.seek(0)

        cleaned_data['images'] = files
        return cleaned_data