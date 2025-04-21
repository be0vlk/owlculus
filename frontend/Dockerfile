FROM node:18

WORKDIR /app
COPY . .

RUN npm install --no-optional

EXPOSE 5174
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]