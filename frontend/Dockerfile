FROM nginx:alpine

# Supprime la config par défaut
RUN rm /etc/nginx/conf.d/default.conf

# Copie notre config nginx
COPY nginx.conf /etc/nginx/conf.d/

# Copie les fichiers statiques dans l'image
COPY . /usr/share/nginx/html

