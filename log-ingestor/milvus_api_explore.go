package main

import (
	"fmt"
	"reflect"
	
	// Old client
	oldclient "github.com/milvus-io/milvus-sdk-go/v2/client"
	
	// New client
	newclient "github.com/milvus-io/milvus/client/v2"
)

func main() {
	fmt.Println("=== OLD CLIENT API ===")
	oldType := reflect.TypeOf((*oldclient.Client)(nil)).Elem()
	for i := 0; i < oldType.NumMethod(); i++ {
		method := oldType.Method(i)
		fmt.Printf("%s\n", method.Name)
	}
	
	fmt.Println("\n=== NEW CLIENT API ===")
	newType := reflect.TypeOf((*newclient.Client)(nil)).Elem()
	for i := 0; i < newType.NumMethod(); i++ {
		method := newType.Method(i)
		fmt.Printf("%s\n", method.Name)
	}
}