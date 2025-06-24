FROM golang:1.21-alpine

WORKDIR /app

COPY go.mod ./
RUN go mod download

COPY . .
RUN go mod tidy
RUN go build -o nexus_exporter .

EXPOSE 9103

CMD ["./nexus_exporter"]